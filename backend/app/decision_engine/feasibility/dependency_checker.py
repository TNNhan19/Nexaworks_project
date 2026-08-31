"""Dependency checker — HARD dependency policy.

Business rule (confirmed in BUSINESS_RULES.md):
- Dependency order cannot be violated.
- A work item may not start before its required dependencies are completed.

Important distinction (Phase 2A):
    An unsatisfied HARD dependency does NOT make a work item permanently INFEASIBLE.
    It makes it BLOCKED: the Planner may schedule the prerequisite work first and
    then schedule this item afterward within the same planning horizon.

    INFEASIBLE is reserved for structural impossibilities (e.g. skill not coverable).

    Reason code: DEPENDENCY_NOT_SATISFIED → contributes to BLOCKED (not INFEASIBLE).
"""
from __future__ import annotations

from app.domain.models import WorkItem

from .models import DependencyResult, ReasonItem
from .reason_codes import ReasonCode, Severity


def check_dependencies(
    work_item: WorkItem,
    completed_ids: frozenset[str],
    all_work_ids: frozenset[str],
) -> tuple[DependencyResult, list[ReasonItem]]:
    """Evaluate HARD dependency constraints.

    Parameters
    ----------
    work_item:
        The work item being evaluated.
    completed_ids:
        Set of work item IDs that are already completed.
        Defaults to empty frozenset at base feasibility (most conservative).
    all_work_ids:
        All work item IDs in the dataset — used to distinguish between
        a missing dependency (not in dataset → INVALID_WORK_REFERENCE) vs
        an incomplete dependency (in dataset but not yet done → BLOCKED).

    Returns
    -------
    result:
        ``DependencyResult`` with satisfied flag and lists of required/missing deps.
    blockers:
        ``ReasonItem`` entries with ``DEPENDENCY_NOT_SATISFIED`` severity WARNING
        for each unsatisfied (but valid) dependency.
        These are blockers, not hard failures.
    """
    required = list(work_item.dependencies)
    missing: list[str] = []
    blockers: list[ReasonItem] = []

    for dep_id in required:
        if dep_id in completed_ids:
            continue  # satisfied
        # Dependency exists in the dataset but is not yet completed → BLOCKED
        # (vs not existing at all → that would be caught by reference validation)
        missing.append(dep_id)
        blockers.append(
            ReasonItem(
                code=ReasonCode.DEPENDENCY_NOT_SATISFIED,
                severity=Severity.WARNING,
                work_item_id=work_item.id,
                details={
                    "dependency_id": dep_id,
                    "dependency_exists_in_dataset": dep_id in all_work_ids,
                    "policy": "HARD",
                },
            )
        )

    satisfied = len(missing) == 0
    result = DependencyResult(
        satisfied=satisfied,
        required=required,
        missing=missing,
    )
    return result, blockers
