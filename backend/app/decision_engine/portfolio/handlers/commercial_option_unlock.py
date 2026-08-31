"""Handler for effect.type == 'commercial_option_unlock'.

Business rule (approved V1):
    - HARD availability condition for a commercial option.
    - Trigger NOT satisfied → option is LOCKED (COMMERCIAL_OPTION_LOCKED).
    - Trigger satisfied → option is AVAILABLE (COMMERCIAL_OPTION_UNLOCKED).
    - Does NOT rank, score, or select the option.
    - Phase 2C handles ranking.  Phase 2B only sets availability.
    - Generic: does NOT hard-code any specific option ID.
    - Targets are commercial option IDs, not work item IDs.
"""
from __future__ import annotations

from app.domain.models import PortfolioEffect

from ..context import PortfolioEvaluationContext
from ..models import (
    CommercialOptionState,
    PortfolioEffectEvaluation,
    PortfolioWarning,
)
from ..reason_codes import PortfolioEffectCode, PortfolioEffectSeverity

EFFECT_TYPE = "commercial_option_unlock"


def handle_commercial_option_unlock(
    effect: PortfolioEffect,
    context: PortfolioEvaluationContext,
) -> tuple[PortfolioEffectEvaluation, list[CommercialOptionState]]:
    """Evaluate a commercial_option_unlock effect.

    Parameters
    ----------
    effect:
        The PortfolioEffect with type 'commercial_option_unlock'.
    context:
        Evaluation context; commercial option IDs are checked against
        ``context.all_commercial_option_ids``.

    Returns
    -------
    evaluation:
        Full PortfolioEffectEvaluation record.
    option_states:
        CommercialOptionState for each target option.
    """
    trigger_id = effect.trigger
    trigger_ok = context.trigger_satisfied(trigger_id)

    warnings: list[PortfolioWarning] = []
    option_states: list[CommercialOptionState] = []

    for target_option_id in effect.targets:
        # Validate target reference — option ID, not work item ID
        if not context.commercial_option_exists(target_option_id):
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TARGET,
                    severity=PortfolioEffectSeverity.ERROR,
                    effect_id=effect.id,
                    target_id=target_option_id,
                    details={
                        "target_option_id": target_option_id,
                        "trigger_id": trigger_id,
                        "effect_type": EFFECT_TYPE,
                        "reason": "Target commercial option not found in dataset.",
                    },
                )
            )
            continue

        if trigger_ok:
            code = PortfolioEffectCode.COMMERCIAL_OPTION_UNLOCKED
            available = True
        else:
            code = PortfolioEffectCode.COMMERCIAL_OPTION_LOCKED
            available = False

        option_states.append(
            CommercialOptionState(
                option_id=target_option_id,
                available=available,
                reason_codes=[code],
                details={
                    "trigger_work_item_id": trigger_id,
                    "trigger_satisfied": trigger_ok,
                    "effect_id": effect.id,
                },
            )
        )

        warnings.append(
            PortfolioWarning(
                code=code,
                severity=PortfolioEffectSeverity.WARNING if not available else PortfolioEffectSeverity.INFO,
                effect_id=effect.id,
                target_id=target_option_id,
                details={
                    "target_option_id": target_option_id,
                    "trigger_work_item_id": trigger_id,
                    "trigger_satisfied": trigger_ok,
                    "available": available,
                },
            )
        )

    evaluation = PortfolioEffectEvaluation(
        effect_id=effect.id,
        effect_type=EFFECT_TYPE,
        trigger_work_item_id=trigger_id,
        targets=list(effect.targets),
        trigger_satisfied=trigger_ok,
        deterministic=True,
        applied=trigger_ok,
        option_states=option_states,
        warnings=warnings,
    )
    return evaluation, option_states
