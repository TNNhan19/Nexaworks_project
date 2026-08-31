"""Deadline checker — deadline policy and status classification.

Business rules (confirmed in BUSINESS_RULES.md):

Deadline status classification:
    EXPIRED         → due_date < planning_date
    WITHIN_HORIZON  → planning_date <= due_date <= planning_end
    OUTSIDE_HORIZON → due_date > planning_end

Deadline policy by work item type:
    delivery / internal / incident → SOFT_WITH_PENALTY
        Lateness is allowed but must be flagged as at-risk (WARNING).
        Actual lateness determination requires the Planner's schedule.
        EXPIRED status → WARNING (not a hard failure for these types).

    sales_opportunity → HARD_OR_EXPIRY
        EXPIRED status → OPPORTUNITY_EXPIRED hard failure (INFEASIBLE).
        The opportunity window has passed and the option is no longer available.

Phase 2A limitation:
    DEADLINE_AT_RISK is NOT raised merely because a due date is within the
    planning horizon.  Actual schedule-based lateness (whether the Planner
    fits the work in time) belongs to Phase 2E.  We only classify the
    structural relationship between due_date and the planning window.
"""
from __future__ import annotations

from datetime import date

from app.domain.models import WorkItem

from .models import DeadlineResult, ReasonItem
from .reason_codes import (
    DeadlinePolicy,
    DeadlineStatus,
    ReasonCode,
    Severity,
)

# Work item types treated as sales opportunities (HARD_OR_EXPIRY policy)
_SALES_OPPORTUNITY_TYPES: frozenset[str] = frozenset({"sales_opportunity"})


def _classify_deadline_policy(work_item_type: str) -> DeadlinePolicy:
    """Determine the applicable deadline policy from the work item type."""
    if work_item_type in _SALES_OPPORTUNITY_TYPES:
        return DeadlinePolicy.HARD_OR_EXPIRY
    return DeadlinePolicy.SOFT_WITH_PENALTY


def _classify_deadline_status(
    due_date: date,
    planning_date: date,
    planning_end: date,
) -> DeadlineStatus:
    """Classify due_date relative to the planning window.

    Boundary conditions:
        due_date < planning_date         → EXPIRED
        planning_date <= due_date <= planning_end → WITHIN_HORIZON
        due_date > planning_end          → OUTSIDE_HORIZON
    """
    if due_date < planning_date:
        return DeadlineStatus.EXPIRED
    if due_date <= planning_end:
        return DeadlineStatus.WITHIN_HORIZON
    return DeadlineStatus.OUTSIDE_HORIZON


def check_deadline(
    work_item: WorkItem,
    planning_date: date,
    planning_end: date,
) -> tuple[DeadlineResult, list[ReasonItem]]:
    """Classify the work item's deadline and emit relevant reason items.

    Parameters
    ----------
    work_item:
        The work item being evaluated.
    planning_date:
        Start date of the planning horizon (reference for expiry checks).
    planning_end:
        End date of the planning horizon.

    Returns
    -------
    result:
        ``DeadlineResult`` with policy, status, and date metadata.
    findings:
        For HARD_OR_EXPIRY + EXPIRED → hard failure (OPPORTUNITY_EXPIRED).
        For SOFT_WITH_PENALTY + EXPIRED → warning only.
        No findings emitted for WITHIN_HORIZON or OUTSIDE_HORIZON at this phase.
    """
    policy = _classify_deadline_policy(work_item.type)
    status = _classify_deadline_status(work_item.due_date, planning_date, planning_end)
    days_until_due = (work_item.due_date - planning_date).days

    result = DeadlineResult(
        policy=policy,
        status=status,
        due_date=work_item.due_date,
        planning_date=planning_date,
        planning_end=planning_end,
        days_until_due=days_until_due,
    )

    findings: list[ReasonItem] = []

    if status == DeadlineStatus.EXPIRED:
        if policy == DeadlinePolicy.HARD_OR_EXPIRY:
            # Sales opportunity: window has closed → hard failure
            findings.append(
                ReasonItem(
                    code=ReasonCode.OPPORTUNITY_EXPIRED,
                    severity=Severity.ERROR,
                    work_item_id=work_item.id,
                    details={
                        "due_date": str(work_item.due_date),
                        "planning_date": str(planning_date),
                        "days_expired": abs(days_until_due),
                        "work_item_type": work_item.type,
                        "policy": policy.value,
                    },
                )
            )
        else:
            # Contract/internal: expired but soft — warn, do not block/infeasible
            findings.append(
                ReasonItem(
                    code=ReasonCode.DEADLINE_AT_RISK,
                    severity=Severity.WARNING,
                    work_item_id=work_item.id,
                    details={
                        "due_date": str(work_item.due_date),
                        "planning_date": str(planning_date),
                        "days_expired": abs(days_until_due),
                        "work_item_type": work_item.type,
                        "policy": policy.value,
                        "note": "Due date already passed; late penalty may apply.",
                    },
                )
            )

    # Note: WITHIN_HORIZON and OUTSIDE_HORIZON generate no findings at Phase 2A.
    # DEADLINE_AT_RISK based on schedule fit belongs to Phase 2E (Planner).

    return result, findings
