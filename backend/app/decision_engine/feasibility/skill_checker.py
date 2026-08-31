"""Skill coverage checker — TEAM_COVERAGE policy.

Business rule (confirmed in BUSINESS_RULES.md):
- Each required skill must be met by at least one individual person.
- Skill levels for the same skill MUST NOT be summed across people.
- Different required skills MAY be covered by different people.

Example:
    Work requires: AI >= 4, Project Management >= 4
    Person A: AI=5 → covers AI
    Person B: PM=4  → covers Project Management
    → Both skills covered. Valid.

    Person A: AI=3, Person B: AI=3
    → AI NOT covered (3+3 ≠ 6; neither individually meets >= 4). Invalid.
"""
from __future__ import annotations

from app.domain.models import Person, SkillRequirement

from .models import ReasonItem, SkillCoverageDetail
from .reason_codes import ReasonCode, Severity


def check_skill_coverage(
    work_item_id: str,
    required_skills: list[SkillRequirement],
    people: list[Person],
) -> tuple[list[SkillCoverageDetail], list[ReasonItem]]:
    """Evaluate TEAM_COVERAGE for each required skill.

    Parameters
    ----------
    work_item_id:
        ID of the work item being evaluated (used to populate reason items).
    required_skills:
        List of ``SkillRequirement`` objects from the work item.
    people:
        All people in the dataset (no pre-filtering by caller).

    Returns
    -------
    details:
        One ``SkillCoverageDetail`` per required skill.
    failures:
        ``ReasonItem`` with code ``MISSING_SKILL_COVERAGE`` for each uncovered skill.
    """
    details: list[SkillCoverageDetail] = []
    failures: list[ReasonItem] = []

    for req in required_skills:
        eligible: list[str] = []
        best_level: float | None = None

        for person in people:
            person_level = person.skills.get(req.skill)
            if person_level is None:
                continue
            # Track best available level across all people (for evidence)
            if best_level is None or person_level > best_level:
                best_level = person_level
            # TEAM_COVERAGE: individual must meet threshold — no summation
            if person_level >= req.min_level:
                eligible.append(person.id)

        covered = len(eligible) > 0

        details.append(
            SkillCoverageDetail(
                skill=req.skill,
                required_level=req.min_level,
                covered=covered,
                eligible_people=eligible,
                best_available_level=best_level,
            )
        )

        if not covered:
            failures.append(
                ReasonItem(
                    code=ReasonCode.MISSING_SKILL_COVERAGE,
                    severity=Severity.ERROR,
                    work_item_id=work_item_id,
                    details={
                        "skill": req.skill,
                        "required_level": req.min_level,
                        "best_available_level": best_level,
                    },
                )
            )

    return details, failures
