"""Phase 2G read-only validation functions.

Each validator receives frozen upstream result objects and returns a list of
ExplanationRecords.  No upstream object is ever mutated.

Validators check:
  A. Mandatory work completeness
  B. Dependency ordering in schedule
  C. Skill coverage on assignments
  D. Language coverage on assignments
  E. Person horizon capacity (no excess)
  F. Daily per-person capacity (no excess)
  G. Unavailable-day scheduling
  H. Shared-resource capacity ceiling
  I. Exclusive-resource double-booking
  J. Commercial exclusivity (max 1 option per opportunity)
  K. Option unlock / expiry at selection
  L. Earliest-start dates respected
  M. Planner NO_BID + selected option conflict
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from app.domain.models import CandidateDataset

from app.decision_engine.planner.models import PlanResult
from app.decision_engine.planner.reason_codes import AssignmentRole, DecisionType, PlannerReasonCode

from .models import ExplanationRecord
from .reason_codes import ExplanationCode, FindingSeverity, SourcePhase

_EPS = 1e-6


def _rec(
    code: ExplanationCode,
    severity: FindingSeverity,
    source_phase: SourcePhase = SourcePhase.FINAL_VALIDATION,
    source_id: str | None = None,
    action_id: str | None = None,
    **evidence: Any,
) -> ExplanationRecord:
    return ExplanationRecord(
        code=code,
        severity=severity,
        source_phase=source_phase,
        source_id=source_id,
        action_id=action_id,
        evidence=dict(evidence),
    )


# ---------------------------------------------------------------------------
# A. Mandatory work completeness
# ---------------------------------------------------------------------------

def validate_mandatory_work(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify every mandatory item is either selected or explicitly marked infeasible."""
    findings: list[ExplanationRecord] = []
    mandatory_ids = {item.id for item in dataset.work_items if item.mandatory}
    selected_ids = set(plan.selected_actions)
    infeasible_ids = set(plan.mandatory_infeasible)

    for wid in mandatory_ids:
        # Check across decisions Ã¢â‚¬â€ some mandatory items may appear as ENABLING_PREREQUISITE
        decided = {dec.work_item_id for dec in plan.decisions}
        if wid in selected_ids or wid in infeasible_ids:
            continue
        if wid not in decided:
            findings.append(_rec(
                ExplanationCode.MANDATORY_WORK_OMITTED,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.FINAL_VALIDATION,
                source_id=wid,
                mandatory=True,
                note="mandatory item not found in selected_actions or mandatory_infeasible",
            ))
    return findings


# ---------------------------------------------------------------------------
# B. Dependency ordering
# ---------------------------------------------------------------------------

def validate_dependency_ordering(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Validate canonical dependencies against the authoritative plan schedule.

    The planner schedules by action ID, while canonical dependencies refer to
    work-item IDs. Selected decisions provide that mapping; ``schedule``
    provides the dates. Optional date fields in ``PlanDecision.details`` are
    deliberately not consulted.
    """
    findings: list[ExplanationRecord] = []
    work_map = {item.id: item for item in dataset.work_items}

    schedule_dates: dict[str, list[date]] = defaultdict(list)
    for entry in plan.schedule:
        schedule_dates[entry.action_id].append(entry.date)
    schedule_bounds = {
        action_id: (min(dates), max(dates))
        for action_id, dates in schedule_dates.items()
    }

    selected_types = {
        DecisionType.DO,
        DecisionType.ENABLING_PREREQUISITE,
        DecisionType.SELECT_OPTION,
    }
    selected_decisions = sorted(
        (dec for dec in plan.decisions if dec.decision in selected_types),
        key=lambda dec: (dec.work_item_id, dec.action_id),
    )
    decision_by_work_id = {dec.work_item_id: dec for dec in selected_decisions}

    for dependent_decision in selected_decisions:
        wid = dependent_decision.work_item_id
        item = work_map.get(wid)
        if item is None or not item.dependencies:
            continue

        dependent_bounds = schedule_bounds.get(dependent_decision.action_id)
        if dependent_bounds is None:
            findings.append(_rec(
                ExplanationCode.SELECTED_ACTION_SCHEDULE_MISSING,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.PLANNER,
                source_id=wid,
                action_id=dependent_decision.action_id,
                schedule_role="dependent",
                dependency_ids=list(item.dependencies),
                note="selected dependent has no schedule records",
            ))
            continue

        dependent_start = dependent_bounds[0]
        for dependency_id in item.dependencies:
            predecessor_decision = decision_by_work_id.get(dependency_id)
            if predecessor_decision is None:
                # The prerequisite may have completed before this plan horizon.
                continue

            predecessor_bounds = schedule_bounds.get(predecessor_decision.action_id)
            if predecessor_bounds is None:
                findings.append(_rec(
                    ExplanationCode.SELECTED_ACTION_SCHEDULE_MISSING,
                    FindingSeverity.ERROR,
                    source_phase=SourcePhase.PLANNER,
                    source_id=dependency_id,
                    action_id=predecessor_decision.action_id,
                    schedule_role="predecessor",
                    required_by_work_item_id=wid,
                    required_by_action_id=dependent_decision.action_id,
                    note="selected predecessor has no schedule records",
                ))
                continue

            predecessor_completion = predecessor_bounds[1]
            if predecessor_completion >= dependent_start:
                findings.append(_rec(
                    ExplanationCode.DEPENDENCY_ORDER_VIOLATION,
                    FindingSeverity.ERROR,
                    source_phase=SourcePhase.PLANNER,
                    source_id=wid,
                    action_id=dependent_decision.action_id,
                    dependency_id=dependency_id,
                    dependency_action_id=predecessor_decision.action_id,
                    dep_completion_date=str(predecessor_completion),
                    dependent_start_date=str(dependent_start),
                    note="dependency must complete before dependent starts",
                ))
    return findings


# ---------------------------------------------------------------------------
# C. Skill coverage
# ---------------------------------------------------------------------------

def validate_skill_coverage(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify every contributor is qualified and the team covers every skill."""
    findings: list[ExplanationRecord] = []
    work_map = {item.id: item for item in dataset.work_items}
    person_map = {person.id: person for person in dataset.people}

    action_assignments: dict[str, list] = defaultdict(list)
    for assignment in plan.assignments:
        action_assignments[assignment.action_id].append(assignment)

    for dec in plan.decisions:
        if dec.decision not in {
            DecisionType.DO, DecisionType.ENABLING_PREREQUISITE, DecisionType.SELECT_OPTION
        }:
            continue
        item = work_map.get(dec.work_item_id)
        if item is None:
            continue

        assignments = action_assignments.get(dec.action_id, [])
        owner_assignments = [
            assignment for assignment in assignments
            if assignment.assignment_role == AssignmentRole.OWNER
        ]
        qualified_owners = [
            assignment.person_id
            for assignment in owner_assignments
            if assignment.person_id in person_map
            and (
                not item.required_skills
                or any(
                    person_map[assignment.person_id].skills.get(req.skill, 0) >= req.min_level
                    for req in item.required_skills
                )
            )
        ]
        if assignments and not qualified_owners:
            findings.append(_rec(
                ExplanationCode.SKILL_COVERAGE_VIOLATION,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.FINAL_VALIDATION,
                source_id=item.id,
                action_id=dec.action_id,
                violation_type="MISSING_QUALIFIED_OWNER",
                owner_people=[assignment.person_id for assignment in owner_assignments],
            ))

        if not item.required_skills:
            continue

        assigned_people = [
            person_map[assignment.person_id]
            for assignment in assignments
            if assignment.person_id in person_map
        ]

        for assignment in assignments:
            person = person_map.get(assignment.person_id)
            if person is None:
                continue
            matched_skills = [
                req.skill for req in item.required_skills
                if person.skills.get(req.skill, 0) >= req.min_level
            ]
            if not matched_skills:
                findings.append(_rec(
                    ExplanationCode.SKILL_COVERAGE_VIOLATION,
                    FindingSeverity.ERROR,
                    source_phase=SourcePhase.FINAL_VALIDATION,
                    source_id=item.id,
                    action_id=dec.action_id,
                    violation_type="UNQUALIFIED_ASSIGNEE",
                    person_id=person.id,
                    required_skills=[req.skill for req in item.required_skills],
                ))

        for req in item.required_skills:
            covered = any(
                person.skills.get(req.skill, 0) >= req.min_level
                for person in assigned_people
            )
            if not covered:
                best = max(
                    (person.skills.get(req.skill, 0) for person in assigned_people),
                    default=None,
                )
                findings.append(_rec(
                    ExplanationCode.SKILL_COVERAGE_VIOLATION,
                    FindingSeverity.ERROR,
                    source_phase=SourcePhase.FINAL_VALIDATION,
                    source_id=item.id,
                    action_id=dec.action_id,
                    violation_type="TEAM_SKILL_GAP",
                    skill=req.skill,
                    required_level=req.min_level,
                    best_available_level=best,
                    assigned_people=[person.id for person in assigned_people],
                ))
    return findings

# ---------------------------------------------------------------------------
# D. Language coverage
# ---------------------------------------------------------------------------

def validate_language_coverage(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify that one execution-qualified owner covers all required languages."""
    findings: list[ExplanationRecord] = []
    from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS
    assumptions = DEFAULT_ASSUMPTIONS
    work_map = {item.id: item for item in dataset.work_items}
    person_map = {person.id: person for person in dataset.people}

    action_assignments: dict[str, list] = defaultdict(list)
    for assignment in plan.assignments:
        action_assignments[assignment.action_id].append(assignment)

    for dec in plan.decisions:
        if dec.decision not in {
            DecisionType.DO, DecisionType.ENABLING_PREREQUISITE, DecisionType.SELECT_OPTION
        }:
            continue
        item = work_map.get(dec.work_item_id)
        if item is None or not item.required_languages:
            continue

        assignments = action_assignments.get(dec.action_id, [])
        owner_assignments = [
            assignment for assignment in assignments
            if assignment.assignment_role == AssignmentRole.OWNER
        ]
        valid_owners: list[str] = []
        for assignment in owner_assignments:
            person = person_map.get(assignment.person_id)
            if person is None:
                continue
            has_execution_skill = (
                not item.required_skills
                or any(
                    person.skills.get(req.skill, 0) >= req.min_level
                    for req in item.required_skills
                )
            )
            has_languages = all(
                language in person.languages for language in item.required_languages
            )
            proxy = assumptions.language_customer_facing_skill
            has_customer_facing_skill = (
                proxy is None
                or not item.required_languages
                or person.skills.get(proxy, 0) >= assumptions.language_customer_facing_min_level
            )
            if has_execution_skill and has_languages and has_customer_facing_skill:
                valid_owners.append(person.id)

        if not valid_owners:
            findings.append(_rec(
                ExplanationCode.LANGUAGE_COVERAGE_VIOLATION,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.FINAL_VALIDATION,
                source_id=item.id,
                action_id=dec.action_id,
                violation_type="MISSING_QUALIFIED_OWNER",
                required_languages=item.required_languages,
                owner_people=[assignment.person_id for assignment in owner_assignments],
                assigned_people=[assignment.person_id for assignment in assignments],
                customer_facing_skill=assumptions.language_customer_facing_skill,
                customer_facing_min_level=assumptions.language_customer_facing_min_level,
            ))
    return findings

# ---------------------------------------------------------------------------
# E. Person horizon capacity
# ---------------------------------------------------------------------------

def validate_person_capacity(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify no person's used_hours exceeds their horizon capacity_hours."""
    findings: list[ExplanationRecord] = []
    for usage in plan.person_capacity:
        if usage.used_hours > usage.capacity_hours + _EPS:
            findings.append(_rec(
                ExplanationCode.PERSON_CAPACITY_EXCEEDED,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.PLANNER,
                source_id=usage.person_id,
                capacity_hours=usage.capacity_hours,
                used_hours=usage.used_hours,
                excess_hours=usage.used_hours - usage.capacity_hours,
            ))
    return findings


# ---------------------------------------------------------------------------
# F. Daily per-person capacity
# ---------------------------------------------------------------------------

def validate_daily_capacity(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify no person is scheduled more hours on a given day than their
    daily capacity (computed from horizon capacity / available days)."""
    findings: list[ExplanationRecord] = []
    # Build daily_capacity per person from plan.person_capacity
    daily_cap: dict[str, float] = {
        usage.person_id: usage.daily_capacity_hours
        for usage in plan.person_capacity
        if usage.available_days > 0
    }
    # Aggregate scheduled hours per person per day
    daily_used: dict[tuple[str, date], float] = defaultdict(float)
    for entry in plan.schedule:
        daily_used[(entry.person_id, entry.date)] += entry.hours

    for (person_id, day), used in daily_used.items():
        cap = daily_cap.get(person_id, 0.0)
        if cap > 0 and used > cap + _EPS:
            findings.append(_rec(
                ExplanationCode.DAILY_CAPACITY_EXCEEDED,
                FindingSeverity.WARNING,
                source_phase=SourcePhase.PLANNER,
                source_id=person_id,
                date=str(day),
                daily_capacity_hours=cap,
                scheduled_hours=used,
                excess_hours=used - cap,
            ))
    return findings


# ---------------------------------------------------------------------------
# G. Unavailable-day scheduling
# ---------------------------------------------------------------------------

def validate_unavailable_days(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify no person is scheduled on a day they are unavailable."""
    findings: list[ExplanationRecord] = []
    person_map = {person.id: person for person in dataset.people}

    # Build unavailable date sets per person
    unavailable: dict[str, set[date]] = {}
    for person in dataset.people:
        dates: set[date] = set()
        for rng in (person.unavailable_ranges or []):
            start = rng.start if isinstance(rng.start, date) else date.fromisoformat(str(rng.start))
            end = rng.end if isinstance(rng.end, date) else date.fromisoformat(str(rng.end))
            d = start
            while d <= end:
                dates.add(d)
                d += timedelta(days=1)
        unavailable[person.id] = dates

    for entry in plan.schedule:
        unavail = unavailable.get(entry.person_id, set())
        if entry.date in unavail:
            findings.append(_rec(
                ExplanationCode.UNAVAILABLE_DAY_SCHEDULED,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.PLANNER,
                source_id=entry.person_id,
                action_id=entry.action_id,
                date=str(entry.date),
                hours=entry.hours,
            ))
    return findings


# ---------------------------------------------------------------------------
# H. Resource capacity ceiling
# ---------------------------------------------------------------------------

def validate_resource_capacity(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify no shared resource's used_hours exceeds its capacity ceiling."""
    findings: list[ExplanationRecord] = []
    for usage in plan.resource_capacity:
        if usage.used_hours > usage.capacity_hours + _EPS:
            findings.append(_rec(
                ExplanationCode.RESOURCE_CAPACITY_EXCEEDED,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.PLANNER,
                source_id=usage.resource_id,
                capacity_hours=usage.capacity_hours,
                used_hours=usage.used_hours,
                excess_hours=usage.used_hours - usage.capacity_hours,
            ))
    return findings


# ---------------------------------------------------------------------------
# I. Exclusive-resource double-booking
# ---------------------------------------------------------------------------

def validate_resource_exclusivity(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify that exclusive resources are not used by two different actions
    on the same day."""
    findings: list[ExplanationRecord] = []
    exclusive_ids = {
        resource.id for resource in dataset.shared_resources if resource.exclusive
    }
    # Map (resource_id, date) -> list of action_ids
    occupancy: dict[tuple[str, date], list[str]] = defaultdict(list)
    for entry in plan.resource_schedule:
        if entry.resource_id in exclusive_ids:
            occupancy[(entry.resource_id, entry.date)].append(entry.action_id)

    for (resource_id, day), action_ids in occupancy.items():
        unique = sorted(set(action_ids))
        if len(unique) > 1:
            findings.append(_rec(
                ExplanationCode.RESOURCE_EXCLUSIVITY_VIOLATION,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.PLANNER,
                source_id=resource_id,
                date=str(day),
                conflicting_action_ids=unique,
                policy="ONE_ACTIVE_WORK_ITEM_PER_RESOURCE_PER_DAY",
            ))
    return findings


# ---------------------------------------------------------------------------
# J. Commercial exclusivity
# ---------------------------------------------------------------------------

def validate_commercial_exclusivity(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify at most one option per opportunity is selected (MUTUALLY_EXCLUSIVE)."""
    findings: list[ExplanationRecord] = []
    # Map work_item_id -> list of selected option decisions
    selected_per_work: dict[str, list[str]] = defaultdict(list)
    no_bid_works: set[str] = set()
    for dec in plan.decisions:
        if dec.decision == DecisionType.SELECT_OPTION:
            option_id = dec.selected_option_id or dec.action_id
            selected_per_work[dec.work_item_id].append(option_id)
        elif dec.decision == DecisionType.NO_BID:
            no_bid_works.add(dec.work_item_id)

    # Check multiple selections
    for wid, option_ids in selected_per_work.items():
        if len(option_ids) > 1:
            findings.append(_rec(
                ExplanationCode.COMMERCIAL_EXCLUSIVITY_VIOLATION,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.FINAL_VALIDATION,
                source_id=wid,
                selected_option_ids=option_ids,
                policy="MUTUALLY_EXCLUSIVE",
            ))

    # Check NO_BID + selected option conflict
    for wid in no_bid_works:
        if wid in selected_per_work:
            findings.append(_rec(
                ExplanationCode.NO_BID_CONFLICTS_WITH_SELECTED_OPTION,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.FINAL_VALIDATION,
                source_id=wid,
                selected_option_ids=selected_per_work[wid],
            ))
    return findings


# ---------------------------------------------------------------------------
# K. Option unlock / expiry at selection
# ---------------------------------------------------------------------------

def validate_option_unlock_and_expiry(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify selected options were unlocked and not expired at selection time."""
    findings: list[ExplanationRecord] = []
    work_map = {item.id: item for item in dataset.work_items}
    planning_start = dataset.metadata.planning_start

    for dec in plan.decisions:
        if dec.decision != DecisionType.SELECT_OPTION:
            continue
        work_item = work_map.get(dec.work_item_id)
        if work_item is None:
            continue
        # Expiry check: sales_opportunity with due_date < planning_start
        if work_item.type == "sales_opportunity" and work_item.due_date < planning_start:
            findings.append(_rec(
                ExplanationCode.OPTION_EXPIRED_AT_SELECTION,
                FindingSeverity.CRITICAL,
                source_phase=SourcePhase.FINAL_VALIDATION,
                source_id=dec.action_id,
                work_item_id=dec.work_item_id,
                due_date=str(work_item.due_date),
                planning_start=str(planning_start),
            ))

    return findings


# ---------------------------------------------------------------------------
# L. Earliest-start respected
# ---------------------------------------------------------------------------

def validate_earliest_start(dataset: CandidateDataset, plan: PlanResult) -> list[ExplanationRecord]:
    """Verify scheduled start_date >= work_item.earliest_start."""
    findings: list[ExplanationRecord] = []
    work_map = {item.id: item for item in dataset.work_items}

    for dec in plan.decisions:
        if dec.decision not in {
            DecisionType.DO, DecisionType.ENABLING_PREREQUISITE, DecisionType.SELECT_OPTION
        }:
            continue
        item = work_map.get(dec.work_item_id)
        if item is None:
            continue
        sd = dec.details.get("start_date")
        if sd is None:
            continue
        start = sd if isinstance(sd, date) else date.fromisoformat(str(sd))
        if start < item.earliest_start:
            findings.append(_rec(
                ExplanationCode.EARLIEST_START_VIOLATED,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.PLANNER,
                source_id=dec.work_item_id,
                action_id=dec.action_id,
                scheduled_start=str(start),
                earliest_start=str(item.earliest_start),
            ))
    return findings
