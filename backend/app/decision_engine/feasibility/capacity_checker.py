"""Skill-eligible person-hour capacity policy.

Every assigned person must satisfy at least one required skill. Work without
required skills may use the full team. Skill coverage across the resulting
team is still validated separately.
"""
from __future__ import annotations

from app.domain.models import Person, SkillRequirement

from .models import CapacityResult, ReasonItem
from .reason_codes import ReasonCode, Severity


def _eligible_people(
    people: list[Person],
    required_skills: list[SkillRequirement],
) -> list[Person]:
    if not required_skills:
        return people
    return [
        person for person in people
        if any(person.skills.get(req.skill, 0) >= req.min_level for req in required_skills)
    ]


def check_capacity(
    work_item_id: str,
    required_hours: float,
    people: list[Person],
    required_skills: list[SkillRequirement] | None = None,
) -> tuple[CapacityResult, list[ReasonItem]]:
    """Evaluate capacity using only people eligible to contribute to the work."""
    requirements = required_skills or []
    eligible = _eligible_people(people, requirements)
    eligible_capacity = sum(person.capacity_hours for person in eligible)
    sufficient = eligible_capacity >= required_hours

    result = CapacityResult(
        required_hours=required_hours,
        total_team_capacity_hours=eligible_capacity,
        sufficient=sufficient,
        note=(
            "Capacity pool: people satisfying at least one required skill."
            if requirements else
            "Capacity pool: all people because the work has no required skills."
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
                    "eligible_capacity_hours": eligible_capacity,
                    "eligible_person_ids": [person.id for person in eligible],
                    "shortfall_hours": required_hours - eligible_capacity,
                },
            )
        )
    return result, failures
