"""Capacity checker — TOTAL_PERSON_HOURS policy.

Business rule (confirmed in BUSINESS_RULES.md):
- required_hours is a shared person-hour pool across all assigned people.
- Capacity check uses the ENTIRE team as the candidate pool.
- Skill/language coverage and total person-hour capacity are ORTHOGONAL concerns.

Rationale:
    A person may contribute labour hours to a work item even if another team
    member is the one satisfying the skill/language threshold.
    Therefore restricting the capacity pool to skill-eligible people only would
    undercount available capacity and produce false INFEASIBLE results.

    Example:
        Work: AI >= 4, required_hours = 100
        Person A: AI=5 → covers the skill threshold
        Person B: AI=1 → cannot cover the skill, but CAN contribute hours

    Both A and B's hours count toward the 100h requirement.

Phase 2A limitation:
    This is structural capacity (total hours across the planning horizon).
    Schedule-based conflicts and individual utilisation optimisation are
    handled by the Planner (Phase 2E).

Work items with no required skills / languages:
    Handled correctly — the full team capacity is used regardless.
"""
from __future__ import annotations

from app.domain.models import Person

from .models import CapacityResult, ReasonItem
from .reason_codes import ReasonCode, Severity


def check_capacity(
    work_item_id: str,
    required_hours: float,
    people: list[Person],
) -> tuple[CapacityResult, list[ReasonItem]]:
    """Evaluate TOTAL_PERSON_HOURS capacity against the entire team pool.

    Parameters
    ----------
    work_item_id:
        ID of the work item (for reason item population).
    required_hours:
        Total person-hours the work item needs.
    people:
        All people in the dataset — the full team is always the capacity pool.

    Returns
    -------
    result:
        ``CapacityResult`` with total team capacity and sufficiency flag.
    failures:
        ``ReasonItem`` with ``INSUFFICIENT_PERSON_CAPACITY`` if capacity is
        structurally insufficient (hard failure → INFEASIBLE).
    """
    total_capacity = sum(p.capacity_hours for p in people)
    sufficient = total_capacity >= required_hours

    result = CapacityResult(
        required_hours=required_hours,
        total_team_capacity_hours=total_capacity,
        sufficient=sufficient,
        note=(
            "Capacity pool: all people in dataset. "
            "Skill/language coverage is evaluated separately."
        ),
    )

    failures: list[ReasonItem] = []
    if not sufficient:
        failures.append(
            ReasonItem(
                code=ReasonCode.INSUFFICIENT_PERSON_CAPACITY,
                severity=Severity.ERROR,
                work_item_id=work_item_id,
                details={
                    "required_hours": required_hours,
                    "total_team_capacity_hours": total_capacity,
                    "shortfall_hours": required_hours - total_capacity,
                },
            )
        )

    return result, failures
