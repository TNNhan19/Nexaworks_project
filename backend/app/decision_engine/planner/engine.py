"""Phase 2E deterministic constraint-aware heuristic planner."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS, AssumptionRegistry
from app.decision_engine.commercial import (
    CommercialEvaluationEngine,
    OptionAvailabilityStatus,
    OptionDeliverabilityStatus,
)
from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.scoring import ScoringEngine, ScoringReference, ScoringResult
from app.domain.models import CandidateDataset, CommercialOption, WorkItem

from .models import (
    Assignment,
    PersonCapacityUsage,
    PlanDecision,
    PlannerWarning,
    PlanResult,
    ResourceCapacityUsage,
)
from .prerequisites import PrerequisiteResolver
from .reason_codes import AllocationType, AssignmentRole, DecisionType, PlannerReasonCode, PlanStatus
from .scheduler import DayScheduler


class PlannerEngine:
    """Build a reproducible four-week plan using hard constraints plus soft score order."""

    def __init__(self, assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS) -> None:
        self.assumptions = assumptions
        self.portfolio_engine = PortfolioEffectsEngine()
        self.commercial_engine = CommercialEvaluationEngine()
        self.feasibility_engine = FeasibilityEngine(assumptions)
        self.scoring_engine = ScoringEngine(assumptions)

    def _mandatory_capacity_pressure(self, item: WorkItem) -> float:
        """Return required hours per structurally eligible capacity hour."""
        if not item.required_skills:
            eligible_capacity = sum(person.capacity_hours for person in self.dataset.people)
        else:
            eligible_capacity = sum(
                person.capacity_hours
                for person in self.dataset.people
                if any(
                    person.skills.get(requirement.skill, 0) >= requirement.min_level
                    for requirement in item.required_skills
                )
            )
        if eligible_capacity <= 0:
            return float("inf")
        return item.required_hours / eligible_capacity

    def plan(
        self,
        dataset: CandidateDataset,
        *,
        completed_work_item_ids: frozenset[str] | None = None,
        scoring_reference: ScoringReference | None = None,
        deferred_work_item_ids: frozenset[str] | None = None,
    ) -> PlanResult:
        self.dataset = dataset
        self.deferred_work_item_ids = frozenset(deferred_work_item_ids or frozenset())
        self.initial_completed = frozenset(completed_work_item_ids or frozenset())
        self.work = {item.id: item for item in dataset.work_items}
        self.options = {item.option_id: item for item in dataset.commercial_options}
        self.options_by_work: dict[str, list[CommercialOption]] = {}
        for option in dataset.commercial_options:
            self.options_by_work.setdefault(option.work_item_id, []).append(option)
        self.resolver = PrerequisiteResolver(dataset)
        self.scheduler = DayScheduler(dataset, self.assumptions)
        self.selected_actions: list[str] = []
        self.selected_work_ids: set[str] = set(self.initial_completed)
        self.selected_options: dict[str, str] = {}
        self.decisions: list[PlanDecision] = []
        self.closures = []
        self.warnings: list[PlannerWarning] = []
        self.unresolved: list[PlannerWarning] = []
        self.coverage: dict[str, dict[str, Any]] = {}
        self.failures: dict[str, PlannerReasonCode] = {}

        baseline_portfolio = self._portfolio(self.initial_completed)
        baseline_commercial = self.commercial_engine.evaluate(
            dataset, baseline_portfolio, completed_ids=self.initial_completed,
        )
        self.scoring: ScoringResult = self.scoring_engine.evaluate(
            dataset,
            baseline_portfolio,
            baseline_commercial,
            scoring_reference=scoring_reference,
            completed_ids=self.initial_completed,
        )
        self.scores = {
            candidate.action_id: candidate.business_value_score
            for candidate in self.scoring.candidates
        }

        # Schedule the most capacity-constrained mandatory commitments first so
        # flexible work cannot consume specialists needed by harder work.
        # Dependency closure still enforces prerequisite order.
        mandatory = sorted(
            (item for item in dataset.work_items if item.mandatory),
            key=lambda item: (
                -self._mandatory_capacity_pressure(item),
                item.due_date,
                item.id,
            ),
        )
        mandatory_infeasible: list[str] = []
        for item in mandatory:
            if item.id in self.selected_work_ids:
                continue
            if self.options_by_work.get(item.id):
                success = self._attempt_best_option(item, mandatory=True)
            else:
                success = self._attempt_action(item.id, mandatory=True)
            if not success:
                mandatory_infeasible.append(item.id)
                self.decisions.append(PlanDecision(
                    work_item_id=item.id,
                    action_id=item.id,
                    decision=DecisionType.MANDATORY_INFEASIBLE,
                    business_value_score=self.scores.get(item.id),
                    reason_codes=[PlannerReasonCode.MANDATORY_INFEASIBLE],
                    details={"failure_code": self.failures.get(item.id)},
                ))

        # Soft ordering only after mandatory closure: score, due date, stable ID.
        candidates = sorted(
            self.scoring.candidates,
            key=lambda candidate: (
                -(candidate.business_value_score or 0.0),
                self.work[candidate.work_item_id].due_date,
                candidate.action_id,
            ),
        )
        for candidate in candidates:
            work_item = self.work[candidate.work_item_id]
            if work_item.mandatory or work_item.id in self.selected_work_ids:
                continue
            if candidate.option_id and work_item.id in self.selected_options:
                continue
            self._attempt_action(candidate.action_id, mandatory=False)

        self._complete_decisions()
        assignments = self._build_assignments()
        person_capacity = self._person_capacity()
        resource_capacity = self._resource_capacity()
        status = (
            PlanStatus.INFEASIBLE if mandatory_infeasible
            else PlanStatus.PARTIAL if any(d.decision in {DecisionType.DELAY, DecisionType.NO_BID} for d in self.decisions)
            else PlanStatus.FEASIBLE
        )
        return PlanResult(
            status=status,
            decisions=self.decisions,
            prerequisite_closures=self.closures,
            assignments=assignments,
            schedule=sorted(
                self.scheduler.state.schedule,
                key=lambda item: (item.date, item.action_id, item.person_id, item.allocation_type.value),
            ),
            resource_schedule=sorted(
                self.scheduler.state.resource_schedule,
                key=lambda item: (item.date, item.resource_id, item.action_id),
            ),
            selected_actions=self.selected_actions,
            delayed_actions=sorted(
                d.action_id for d in self.decisions if d.decision == DecisionType.DELAY
            ),
            no_bid_opportunities=sorted(
                d.work_item_id for d in self.decisions if d.decision == DecisionType.NO_BID
            ),
            mandatory_infeasible=mandatory_infeasible,
            person_capacity=person_capacity,
            resource_capacity=resource_capacity,
            unresolved_blockers=self.unresolved,
            warnings=self.warnings,
            planning_assumptions={
                "daily_capacity_policy": self.assumptions.daily_capacity_policy,
                "unavailable_range_boundary_policy": self.assumptions.unavailable_range_boundary_policy,
                "exclusive_resource_day_policy": self.assumptions.exclusive_resource_day_policy,
                "commercial_delivery_timing_policy": self.assumptions.commercial_delivery_timing_policy,
                "planning_granularity": self.assumptions.planning_granularity,
                "sales_capacity_policy": self.assumptions.sales_capacity_policy,
                "deferred_work_item_ids": sorted(self.deferred_work_item_ids),
            },
            score_version=self.scoring.score_version,
        )

    def _portfolio(self, completed: frozenset[str] | set[str]):
        context = self.portfolio_engine.build_context_from_dataset(
            self.dataset,
            completed_work_item_ids=frozenset(completed),
            selected_work_item_ids=frozenset(self.selected_work_ids),
        )
        return self.portfolio_engine.evaluate(self.dataset, context)

    def _attempt_best_option(self, item: WorkItem, mandatory: bool) -> bool:
        ordered = sorted(
            self.options_by_work[item.id],
            key=lambda option: (-(self.scores.get(option.option_id) or 0.0), option.option_id),
        )
        return any(self._attempt_action(option.option_id, mandatory=mandatory) for option in ordered)

    def _snapshot(self) -> dict[str, Any]:
        return {
            "schedule": self.scheduler.state.clone(),
            "selected_actions": list(self.selected_actions),
            "selected_work_ids": set(self.selected_work_ids),
            "selected_options": dict(self.selected_options),
            "decisions": list(self.decisions),
            "closures": list(self.closures),
            "warnings": list(self.warnings),
            "coverage": deepcopy(self.coverage),
        }

    def _restore(self, snapshot: dict[str, Any]) -> None:
        self.scheduler.restore(snapshot["schedule"])
        self.selected_actions = snapshot["selected_actions"]
        self.selected_work_ids = snapshot["selected_work_ids"]
        self.selected_options = snapshot["selected_options"]
        self.decisions = snapshot["decisions"]
        self.closures = snapshot["closures"]
        self.warnings = snapshot["warnings"]
        self.coverage = snapshot["coverage"]

    def _attempt_action(self, action_id: str, *, mandatory: bool, enabling: bool = False) -> bool:
        option = self.options.get(action_id)
        work_item = self.work.get(option.work_item_id if option else action_id)
        if work_item is None:
            self.failures[action_id] = PlannerReasonCode.INVALID_REFERENCE
            return False
        if work_item.id in self.deferred_work_item_ids:
            self.failures[action_id] = PlannerReasonCode.USER_DEFERRED
            return False
        if work_item.id in self.selected_work_ids:
            return True
        if option is not None and work_item.id in self.selected_options:
            return self.selected_options[work_item.id] == action_id

        snapshot = self._snapshot()
        closure = self.resolver.resolve(action_id)
        if closure.cycle_detected:
            self.failures[action_id] = PlannerReasonCode.DEPENDENCY_CYCLE_DETECTED
            self.unresolved.append(PlannerWarning(
                code=PlannerReasonCode.DEPENDENCY_CYCLE_DETECTED,
                action_id=action_id,
                details={"cycle_path": closure.cycle_path},
            ))
            self.closures.append(closure)
            return False
        if closure.invalid_references:
            self.failures[action_id] = PlannerReasonCode.INVALID_REFERENCE
            self.unresolved.append(PlannerWarning(
                code=PlannerReasonCode.INVALID_REFERENCE,
                action_id=action_id,
                details={"invalid_references": closure.invalid_references},
            ))
            self.closures.append(closure)
            return False

        for prerequisite_id in closure.completion_order:
            if prerequisite_id in self.selected_work_ids:
                continue
            prerequisite = self.work[prerequisite_id]
            if self.options_by_work.get(prerequisite_id):
                ok = self._attempt_best_option(prerequisite, mandatory=False)
            else:
                ok = self._attempt_action(prerequisite_id, mandatory=False, enabling=True)
            if not ok:
                self._restore(snapshot)
                self.closures.append(closure)
                self.failures[action_id] = PlannerReasonCode.DELAYED_PREREQUISITE_NOT_SCHEDULABLE
                return False

        earliest = work_item.earliest_start
        for prerequisite_id in closure.required_prerequisites:
            completed_on = self.scheduler.state.completion_dates.get(prerequisite_id)
            if completed_on is not None:
                earliest = max(earliest, completed_on + timedelta(days=1))

        # If a selected deterministic reducer can finish first, deliberately start
        # the target afterward and rederive its effective hours from canonical data.
        for effect in self.dataset.portfolio_effects:
            if effect.effect.get("type") != "hours_reduction" or work_item.id not in effect.targets:
                continue
            trigger_date = self.scheduler.state.completion_dates.get(effect.trigger)
            if trigger_date is not None:
                earliest = max(earliest, trigger_date + timedelta(days=1))

        completed_before = set(self.initial_completed)
        completed_before.update(
            wid for wid, completed_on in self.scheduler.state.completion_dates.items()
            if completed_on < earliest
        )
        portfolio = self._portfolio(frozenset(completed_before))
        effective_hours = portfolio.get_effective_hours(work_item.id, work_item.required_hours)
        feasibility = self.feasibility_engine.check_work_item(
            work_item,
            self.dataset,
            completed_ids=frozenset(completed_before),
            effective_hours_override={work_item.id: effective_hours},
        )
        if feasibility.status == FeasibilityStatus.INFEASIBLE:
            self._restore(snapshot)
            code = (
                PlannerReasonCode.SALES_OPPORTUNITY_EXPIRED
                if any(item.code.value == "OPPORTUNITY_EXPIRED" for item in feasibility.hard_failures)
                else PlannerReasonCode.DELAYED_HARD_CONSTRAINT
            )
            self.failures[action_id] = code
            return False
        if feasibility.status == FeasibilityStatus.BLOCKED:
            self._restore(snapshot)
            self.failures[action_id] = PlannerReasonCode.DELAYED_PREREQUISITE_NOT_SCHEDULABLE
            return False

        score = self.scores.get(action_id)
        if option is None:
            attempt = self.scheduler.schedule_phase(
                action_id=action_id,
                work_item=work_item,
                hours=effective_hours,
                earliest=max(earliest, self.dataset.metadata.planning_start),
                latest=None,
                allocation_type=AllocationType.WORK,
                use_resources=True,
                require_coverage=True,
            )
            if not attempt.success:
                self._restore(snapshot)
                self.failures[action_id] = attempt.reason_code or PlannerReasonCode.DELAYED_CAPACITY_LIMIT
                return False
            completion = attempt.completion_date
            base_completion = completion
            delivery_hours = 0.0
        else:
            commercial = self.commercial_engine.evaluate(
                self.dataset, portfolio, completed_ids=frozenset(completed_before),
            )
            metrics = commercial.get_option(action_id)
            if metrics is None or metrics.availability in {OptionAvailabilityStatus.EXPIRED, OptionAvailabilityStatus.INVALID}:
                self._restore(snapshot)
                self.failures[action_id] = PlannerReasonCode.DELAYED_HARD_CONSTRAINT
                return False
            if metrics.availability == OptionAvailabilityStatus.LOCKED:
                self._restore(snapshot)
                self.failures[action_id] = PlannerReasonCode.DELAYED_PREREQUISITE_NOT_SCHEDULABLE
                return False
            if metrics.deliverability not in {
                OptionDeliverabilityStatus.INDIVIDUALLY_DELIVERABLE,
            }:
                self._restore(snapshot)
                self.failures[action_id] = PlannerReasonCode.DELAYED_HARD_CONSTRAINT
                return False
            latest = work_item.due_date if work_item.type == "sales_opportunity" else None
            base = self.scheduler.schedule_phase(
                action_id=action_id,
                work_item=work_item,
                hours=effective_hours,
                earliest=max(earliest, self.dataset.metadata.planning_start),
                latest=latest,
                allocation_type=AllocationType.SCHEDULED_BASE_EFFORT,
                use_resources=True,
                require_coverage=True,
            )
            if not base.success:
                self._restore(snapshot)
                self.failures[action_id] = base.reason_code or PlannerReasonCode.DELAYED_CAPACITY_LIMIT
                return False
            delivery_hours = float(metrics.committed_delivery_hours_if_won or 0.0)
            reserved = self.scheduler.schedule_phase(
                action_id=action_id,
                work_item=work_item,
                hours=delivery_hours,
                earliest=base.completion_date or earliest,
                latest=None,
                allocation_type=AllocationType.RESERVED_DELIVERY,
                use_resources=False,
                require_coverage=False,
            )
            if not reserved.success:
                self._restore(snapshot)
                self.failures[action_id] = reserved.reason_code or PlannerReasonCode.DELAYED_CAPACITY_LIMIT
                return False
            attempt = base
            completion = max(base.completion_date, reserved.completion_date)
            base_completion = base.completion_date

        assert completion is not None
        self.scheduler.state.completion_dates[work_item.id] = completion
        self.selected_work_ids.add(work_item.id)
        self.selected_actions.append(action_id)
        if option is not None:
            self.selected_options[work_item.id] = action_id
        self.coverage[action_id] = {
            "skills": attempt.witness_skills,
            "languages": attempt.witness_languages,
            "owner_id": attempt.owner_id,
        }
        reason_codes = []
        if mandatory:
            reason_codes.append(PlannerReasonCode.MANDATORY_SELECTED)
        elif enabling:
            reason_codes.append(PlannerReasonCode.PREREQUISITE_SELECTED)
        else:
            reason_codes.append(PlannerReasonCode.SELECTED_BY_BUSINESS_VALUE)
        if closure.required_prerequisites:
            reason_codes.append(PlannerReasonCode.DEPENDENCY_ORDER_ENFORCED)
        if option is not None and closure.unlock_triggers:
            reason_codes.append(PlannerReasonCode.OPTION_UNLOCKED_IN_PLAN)
        if option is not None and delivery_hours > 0:
            reason_codes.append(PlannerReasonCode.DELIVERY_CAPACITY_RESERVED)
        details: dict[str, Any] = {
            "start_date": attempt.start_date,
            "completion_date": completion,
            "base_completion_date": base_completion,
            "base_required_hours": work_item.required_hours,
            "effective_base_hours": effective_hours,
            "reserved_delivery_hours": delivery_hours,
        }
        if completion > work_item.due_date and work_item.type != "sales_opportunity":
            late_days = (completion - work_item.due_date).days
            reason_codes.append(PlannerReasonCode.SCHEDULED_AFTER_DUE_DATE)
            details["late_days"] = late_days
            details["late_penalty_jpy"] = late_days * work_item.late_penalty_jpy_per_day
            self.warnings.append(PlannerWarning(
                code=PlannerReasonCode.SCHEDULED_AFTER_DUE_DATE,
                action_id=action_id,
                details={"late_days": late_days, "due_date": work_item.due_date},
            ))
        decision_type = (
            DecisionType.SELECT_OPTION if option is not None
            else DecisionType.ENABLING_PREREQUISITE if enabling
            else DecisionType.DO
        )
        self.decisions.append(PlanDecision(
            work_item_id=work_item.id,
            action_id=action_id,
            decision=decision_type,
            selected_option_id=option.option_id if option is not None else None,
            business_value_score=score,
            prerequisite_ids=closure.required_prerequisites,
            unlock_trigger_ids=closure.unlock_triggers,
            reason_codes=reason_codes,
            details=details,
        ))
        self.closures.append(closure)
        return True

    def _complete_decisions(self) -> None:
        decided_actions = {decision.action_id for decision in self.decisions}
        for work_item in self.dataset.work_items:
            options = self.options_by_work.get(work_item.id, [])
            if options:
                selected = self.selected_options.get(work_item.id)
                if selected is None:
                    codes = [PlannerReasonCode.NO_BID_NO_FEASIBLE_OPTION]
                    if any(self.failures.get(option.option_id) == PlannerReasonCode.DELAYED_CAPACITY_LIMIT for option in options):
                        codes = [PlannerReasonCode.NO_BID_CAPACITY_CONSTRAINT]
                    self.decisions.append(PlanDecision(
                        work_item_id=work_item.id,
                        action_id=work_item.id,
                        decision=DecisionType.NO_BID,
                        reason_codes=codes,
                        details={
                            "canonical_option_ids": [option.option_id for option in options],
                            "attempt_failures": {
                                option.option_id: self.failures.get(option.option_id)
                                for option in options if option.option_id in self.failures
                            },
                        },
                    ))
                else:
                    for option in options:
                        if option.option_id == selected or option.option_id in decided_actions:
                            continue
                        self.decisions.append(PlanDecision(
                            work_item_id=work_item.id,
                            action_id=option.option_id,
                            decision=DecisionType.DELAY,
                            business_value_score=self.scores.get(option.option_id),
                            reason_codes=[PlannerReasonCode.MUTUALLY_EXCLUSIVE_ENFORCED],
                            details={"selected_option_id": selected},
                        ))
            elif work_item.id not in self.selected_work_ids and work_item.id not in decided_actions:
                code = self.failures.get(work_item.id, PlannerReasonCode.DELAYED_CAPACITY_LIMIT)
                self.decisions.append(PlanDecision(
                    work_item_id=work_item.id,
                    action_id=work_item.id,
                    decision=DecisionType.DELAY,
                    business_value_score=self.scores.get(work_item.id),
                    reason_codes=[code],
                ))

    def _build_assignments(self) -> list[Assignment]:
        totals: dict[tuple[str, str], float] = {}
        for entry in self.scheduler.state.schedule:
            key = (entry.person_id, entry.action_id)
            totals[key] = totals.get(key, 0.0) + entry.hours

        action_to_work = {
            decision.action_id: decision.work_item_id for decision in self.decisions
        }
        person_map = {person.id: person for person in self.dataset.people}
        result: list[Assignment] = []
        for (person_id, action_id), hours in sorted(
            totals.items(), key=lambda item: (item[0][1], item[0][0])
        ):
            evidence = self.coverage.get(action_id, {})
            person = person_map[person_id]
            work_item = self.work.get(action_to_work.get(action_id, action_id))
            skills_covered = []
            if work_item is not None:
                skills_covered = [
                    req.skill for req in work_item.required_skills
                    if person.skills.get(req.skill, 0) >= req.min_level
                ]
            result.append(Assignment(
                person_id=person_id,
                action_id=action_id,
                assigned_hours=round(hours, 6),
                assignment_role=(
                    AssignmentRole.OWNER
                    if evidence.get("owner_id") == person_id
                    else AssignmentRole.CONTRIBUTOR
                ),
                skills_covered=skills_covered,
                languages_covered=evidence.get("languages", {}).get(person_id, []),
            ))
        return result

    def _person_capacity(self) -> list[PersonCapacityUsage]:
        result: list[PersonCapacityUsage] = []
        for person in self.dataset.people:
            capacities = self.scheduler.state.person_daily_capacity[person.id]
            available = [value for value in capacities.values() if value > 0]
            used = self.scheduler.state.person_total_used[person.id]
            result.append(PersonCapacityUsage(
                person_id=person.id,
                capacity_hours=person.capacity_hours,
                used_hours=round(used, 6),
                remaining_hours=round(max(0.0, person.capacity_hours - used), 6),
                available_days=len(available),
                daily_capacity_hours=round(available[0], 10) if available else 0.0,
            ))
        return result

    def _resource_capacity(self) -> list[ResourceCapacityUsage]:
        return [
            ResourceCapacityUsage(
                resource_id=resource.id,
                capacity_hours=resource.capacity_hours,
                used_hours=round(self.scheduler.state.resource_total_used[resource.id], 6),
                remaining_hours=round(
                    max(0.0, resource.capacity_hours - self.scheduler.state.resource_total_used[resource.id]), 6
                ),
                exclusive=bool(resource.exclusive),
            )
            for resource in self.dataset.shared_resources
        ]
