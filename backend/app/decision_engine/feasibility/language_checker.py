"""Owner language coverage policy.

The owner must satisfy every required language and at least one required skill.
For work without skill requirements, language-qualified people remain eligible.
"""
from __future__ import annotations

from app.decision_engine.assumptions import AssumptionRegistry, DEFAULT_ASSUMPTIONS
from app.domain.models import Person, SkillRequirement

from .models import LanguageCoverageDetail, ReasonItem
from .reason_codes import ReasonCode, Severity


def _is_customer_facing(person: Person, assumptions: AssumptionRegistry) -> bool:
    skill = assumptions.language_customer_facing_skill
    if skill is None:
        return True
    return person.skills.get(skill, 0.0) >= assumptions.language_customer_facing_min_level


def _has_execution_skill(person: Person, requirements: list[SkillRequirement]) -> bool:
    return not requirements or any(
        person.skills.get(req.skill, 0.0) >= req.min_level for req in requirements
    )


def check_language_coverage(
    work_item_id: str,
    required_languages: list[str],
    people: list[Person],
    assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS,
    required_skills: list[SkillRequirement] | None = None,
) -> tuple[list[LanguageCoverageDetail], list[ReasonItem]]:
    """Require one potential owner to cover all mandatory languages."""
    requirements = required_skills or []
    owner_candidates = [
        person for person in people
        if _has_execution_skill(person, requirements)
        and _is_customer_facing(person, assumptions)
        and all(language in person.languages for language in required_languages)
    ]
    eligible_ids = [person.id for person in owner_candidates]
    details: list[LanguageCoverageDetail] = []
    failures: list[ReasonItem] = []

    for language in required_languages:
        covered = bool(owner_candidates)
        details.append(LanguageCoverageDetail(
            language=language,
            covered=covered,
            eligible_people=eligible_ids,
        ))
        if not covered:
            failures.append(ReasonItem(
                code=ReasonCode.MISSING_LANGUAGE_COVERAGE,
                severity=Severity.ERROR,
                work_item_id=work_item_id,
                details={
                    "language": language,
                    "required_languages": required_languages,
                    "owner_must_cover_all_languages": True,
                    "owner_must_cover_execution_skill": bool(requirements),
                    "customer_facing_skill": assumptions.language_customer_facing_skill,
                    "customer_facing_min_level": assumptions.language_customer_facing_min_level,
                    "eligible_speakers_found": 0,
                },
            ))
    return details, failures
