"""Feasibility Engine — Phase 2A orchestrator.

Answers: "For a given work item or candidate action, is it operationally
feasible under the current dataset and assumptions, and if not, exactly why?"

Pipeline per work item:
    1. Skill coverage check     (TEAM_COVERAGE policy)
    2. Language coverage check  (CUSTOMER_FACING_COVERAGE policy)
    3. Dependency check         (HARD policy)
    4. Capacity check           (TOTAL_PERSON_HOURS policy — full team pool)
    5. Resource check           (structural hours vs ceiling)
    6. Deadline check           (SOFT_WITH_PENALTY or HARD_OR_EXPIRY)
    7. Status determination     (INFEASIBLE / BLOCKED / FEASIBLE)
    8. Mandatory item warnings  (MANDATORY_ITEM_INFEASIBLE / MANDATORY_ITEM_BLOCKED)

Status semantics:
    INFEASIBLE  — hard_failures is non-empty (permanent constraint violation)
    BLOCKED     — hard_failures is empty, blockers is non-empty (e.g. HARD dep unsatisfied)
    FEASIBLE    — both lists empty

The engine is:
    - Deterministic: same dataset + assumptions = same result
    - Framework-independent: no FastAPI imports
    - Free of hard-coded dataset IDs, person names, or work item IDs
"""
from __future__ import annotations

from datetime import date

from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS, AssumptionRegistry
from app.domain.models import CandidateDataset, WorkItem

from .capacity_checker import check_capacity
from .deadline_checker import check_deadline
from .dependency_checker import check_dependencies
from .language_checker import check_language_coverage
from .models import FeasibilityResult, ReasonItem
from .reason_codes import FeasibilityStatus, ReasonCode, Severity
from .resource_checker import check_resources
from .skill_checker import check_skill_coverage


def _determine_status(
    hard_failures: list[ReasonItem],
    blockers: list[ReasonItem],
) -> FeasibilityStatus:
    """Derive the overall feasibility status from classified findings."""
    if hard_failures:
        return FeasibilityStatus.INFEASIBLE
    if blockers:
        return FeasibilityStatus.BLOCKED
    return FeasibilityStatus.FEASIBLE


def _mandatory_warnings(
    work_item: WorkItem,
    status: FeasibilityStatus,
) -> list[ReasonItem]:
    """Emit warnings when a mandatory item cannot be satisfied."""
    if not work_item.mandatory:
        return []
    warnings: list[ReasonItem] = []
    if status == FeasibilityStatus.INFEASIBLE:
        warnings.append(
            ReasonItem(
                code=ReasonCode.MANDATORY_ITEM_INFEASIBLE,
                severity=Severity.WARNING,
                work_item_id=work_item.id,
                details={
                    "mandatory": True,
                    "status": status.value,
                    "note": (
                        "This work item is marked mandatory but cannot be satisfied "
                        "under current constraints."
                    ),
                },
            )
        )
    elif status == FeasibilityStatus.BLOCKED:
        warnings.append(
            ReasonItem(
                code=ReasonCode.MANDATORY_ITEM_BLOCKED,
                severity=Severity.WARNING,
                work_item_id=work_item.id,
                details={
                    "mandatory": True,
                    "status": status.value,
                    "note": (
                        "This mandatory work item is BLOCKED by unsatisfied dependencies. "
                        "The Planner must resolve blockers to include it."
                    ),
                },
            )
        )
    return warnings


class FeasibilityEngine:
    """Phase 2A Feasibility Engine.

    Checks whether individual work items are operationally feasible under
    the given dataset and assumption configuration.

    Usage::

        engine = FeasibilityEngine()
        result = engine.check_work_item(work_item, dataset)
        all_results = engine.check_all(dataset)

    The engine does NOT modify the dataset or assumptions — it is pure and
    deterministic.
    """

    def __init__(self, assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS) -> None:
        self._assumptions = assumptions

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_work_item(
        self,
        work_item: WorkItem,
        dataset: CandidateDataset,
        planning_date: date | None = None,
        completed_ids: frozenset[str] | None = None,
        effective_hours_override: dict[str, float] | None = None,
    ) -> FeasibilityResult:
        """Check feasibility of a single work item.

        Parameters
        ----------
        work_item:
            The work item to evaluate.
        dataset:
            Fully validated ``CandidateDataset`` (domain model).
        planning_date:
            Reference date for deadline and expiry checks.
            Defaults to ``dataset.metadata.planning_start``.
        completed_ids:
            Set of work item IDs already completed.
            Defaults to empty frozenset (most conservative assumption).
        effective_hours_override:
            Optional mapping work_item_id → effective_required_hours derived
            from the Portfolio Effects Engine (Phase 2B).  When provided, the
            capacity checker uses the effective hours instead of the canonical
            required_hours.  The engine does NOT need to know WHY the hours
            changed — that trace lives in the PortfolioEffectsResult.
            Defaults to None (use canonical required_hours).

        Returns
        -------
        FeasibilityResult
        """
        if planning_date is None:
            planning_date = dataset.metadata.planning_start
        if completed_ids is None:
            completed_ids = frozenset()

        all_work_ids = frozenset(w.id for w in dataset.work_items)

        # --- 1. Skill coverage ---------------------------------------------------
        skill_details, skill_failures = check_skill_coverage(
            work_item_id=work_item.id,
            required_skills=work_item.required_skills,
            people=dataset.people,
        )

        # --- 2. Language coverage ------------------------------------------------
        lang_details, lang_failures = check_language_coverage(
            work_item_id=work_item.id,
            required_languages=work_item.required_languages,
            people=dataset.people,
            assumptions=self._assumptions,
        )

        # --- 3. Dependency check -------------------------------------------------
        dep_result, dep_blockers = check_dependencies(
            work_item=work_item,
            completed_ids=completed_ids,
            all_work_ids=all_work_ids,
        )

        # --- 4. Capacity check ---------------------------------------------------
        # Full team pool — skill/language coverage is orthogonal to hour capacity.
        # If effective_hours_override is provided (from Portfolio Effects Engine),
        # use the effective hours instead of the canonical required_hours.
        # The feasibility engine does not need to know why hours changed.
        hours_for_capacity = (
            effective_hours_override.get(work_item.id, work_item.required_hours)
            if effective_hours_override is not None
            else work_item.required_hours
        )
        cap_result, cap_failures = check_capacity(
            work_item_id=work_item.id,
            required_hours=hours_for_capacity,
            people=dataset.people,
        )

        # --- 5. Resource check ---------------------------------------------------
        res_results, res_failures = check_resources(
            work_item_id=work_item.id,
            resource_requirements=work_item.resource_requirements,
            shared_resources=dataset.shared_resources,
        )

        # --- 6. Deadline check ---------------------------------------------------
        deadline_result, deadline_findings = check_deadline(
            work_item=work_item,
            planning_date=planning_date,
            planning_end=dataset.metadata.planning_end,
        )

        # --- 7. Classify all findings -------------------------------------------
        # Hard failures → INFEASIBLE
        hard_failures: list[ReasonItem] = (
            skill_failures + lang_failures + cap_failures + res_failures
        )
        # Deadline expiry on sales_opportunity is a hard failure
        # Deadline expiry on other types is a warning (handled below)
        hard_deadline = [
            f for f in deadline_findings if f.severity.value == "ERROR"
        ]
        warn_deadline = [
            f for f in deadline_findings if f.severity.value == "WARNING"
        ]
        hard_failures.extend(hard_deadline)

        # Blockers → BLOCKED (potentially resolvable by Planner)
        blockers: list[ReasonItem] = dep_blockers

        # Warnings (non-fatal)
        warnings: list[ReasonItem] = warn_deadline

        # --- 8. Status -----------------------------------------------------------
        status = _determine_status(hard_failures, blockers)

        # --- 9. Mandatory warnings -----------------------------------------------
        warnings.extend(_mandatory_warnings(work_item, status))

        return FeasibilityResult(
            work_item_id=work_item.id,
            status=status,
            skill_coverage=skill_details,
            language_coverage=lang_details,
            dependencies=dep_result,
            capacity=cap_result,
            resources=res_results,
            deadline=deadline_result,
            hard_failures=hard_failures,
            blockers=blockers,
            warnings=warnings,
        )

    def check_all(
        self,
        dataset: CandidateDataset,
        planning_date: date | None = None,
        completed_ids: frozenset[str] | None = None,
        effective_hours_override: dict[str, float] | None = None,
    ) -> list[FeasibilityResult]:
        """Check feasibility of all work items in the dataset.

        Parameters
        ----------
        dataset:
            Fully validated ``CandidateDataset``.
        planning_date:
            Defaults to ``dataset.metadata.planning_start``.
        completed_ids:
            Defaults to empty frozenset.
        effective_hours_override:
            Optional mapping from Portfolio Effects Engine (Phase 2B).
            See ``check_work_item`` for details.

        Returns
        -------
        list of ``FeasibilityResult``, one per work item, in dataset order.
        """
        if planning_date is None:
            planning_date = dataset.metadata.planning_start
        if completed_ids is None:
            completed_ids = frozenset()

        return [
            self.check_work_item(
                work_item=w,
                dataset=dataset,
                planning_date=planning_date,
                completed_ids=completed_ids,
                effective_hours_override=effective_hours_override,
            )
            for w in dataset.work_items
        ]
