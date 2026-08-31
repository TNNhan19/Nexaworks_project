"""Language coverage checker — CUSTOMER_FACING_COVERAGE policy.

Business rule (confirmed in BUSINESS_RULES.md):
- Required languages need to be covered at the customer-facing / coordination level.
- Not every technical contributor must speak the required language.
- "Customer-facing" is configurable through AssumptionRegistry, not hard-coded.

Configuration via AssumptionRegistry:
    language_customer_facing_skill = None  (default)
        → Any person who speaks the language qualifies.
    language_customer_facing_skill = "project_management"
    language_customer_facing_min_level = 3
        → Only people with project_management >= 3 AND the language qualify.

This keeps the policy data-driven and reusable for unseen datasets.
"""
from __future__ import annotations

from app.decision_engine.assumptions import AssumptionRegistry, DEFAULT_ASSUMPTIONS
from app.domain.models import Person

from .models import LanguageCoverageDetail, ReasonItem
from .reason_codes import ReasonCode, Severity


def _is_customer_facing(person: Person, assumptions: AssumptionRegistry) -> bool:
    """Return True if this person counts as customer-facing under the given policy."""
    skill = assumptions.language_customer_facing_skill
    if skill is None:
        # Default policy: any speaker is considered customer-facing
        return True
    # Configurable policy: person must have the designated coordination skill
    # at or above the configured minimum level
    person_level = person.skills.get(skill, 0.0)
    return person_level >= assumptions.language_customer_facing_min_level


def check_language_coverage(
    work_item_id: str,
    required_languages: list[str],
    people: list[Person],
    assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS,
) -> tuple[list[LanguageCoverageDetail], list[ReasonItem]]:
    """Evaluate CUSTOMER_FACING_COVERAGE for each required language.

    Coverage results are returned separately from skill coverage results so
    the caller can present them independently (as required by the business rule).

    Parameters
    ----------
    work_item_id:
        ID of the work item being evaluated.
    required_languages:
        Language codes required by the work item.
    people:
        All people in the dataset.
    assumptions:
        AssumptionRegistry controlling the customer-facing policy.

    Returns
    -------
    details:
        One ``LanguageCoverageDetail`` per required language.
    failures:
        ``ReasonItem`` with ``MISSING_LANGUAGE_COVERAGE`` for each uncovered language.
    """
    details: list[LanguageCoverageDetail] = []
    failures: list[ReasonItem] = []

    for language in required_languages:
        eligible: list[str] = []

        for person in people:
            if language not in person.languages:
                continue
            if _is_customer_facing(person, assumptions):
                eligible.append(person.id)

        covered = len(eligible) > 0

        details.append(
            LanguageCoverageDetail(
                language=language,
                covered=covered,
                eligible_people=eligible,
            )
        )

        if not covered:
            failures.append(
                ReasonItem(
                    code=ReasonCode.MISSING_LANGUAGE_COVERAGE,
                    severity=Severity.ERROR,
                    work_item_id=work_item_id,
                    details={
                        "language": language,
                        "customer_facing_skill": assumptions.language_customer_facing_skill,
                        "customer_facing_min_level": assumptions.language_customer_facing_min_level,
                        "eligible_speakers_found": 0,
                    },
                )
            )

    return details, failures
