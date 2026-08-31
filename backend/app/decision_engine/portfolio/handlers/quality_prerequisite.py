"""Handler for effect.type == 'quality_prerequisite'.

Business rule (approved V1):
    - qualitative risk flag ONLY
    - does NOT create a hard dependency
    - does NOT block or make INFEASIBLE by itself
    - emits QUALITY_PREREQUISITE_RISK when trigger is NOT satisfied
    - emits QUALITY_PREREQUISITE_SATISFIED when trigger IS satisfied
    - no invented numeric probability reduction
    - no invented rework percentage
"""
from __future__ import annotations

from app.domain.models import PortfolioEffect

from ..context import PortfolioEvaluationContext
from ..models import PortfolioEffectEvaluation, PortfolioWarning
from ..reason_codes import PortfolioEffectCode, PortfolioEffectSeverity

EFFECT_TYPE = "quality_prerequisite"


def handle_quality_prerequisite(
    effect: PortfolioEffect,
    context: PortfolioEvaluationContext,
) -> PortfolioEffectEvaluation:
    """Evaluate a quality_prerequisite effect.

    Emits a QUALITY_PREREQUISITE_RISK warning for each target work item when
    the trigger is not completed.  When the trigger is completed, emits
    QUALITY_PREREQUISITE_SATISFIED (informational) instead.

    No hard failures, no BLOCKED status, no numeric probability invented.
    """
    trigger_id = effect.trigger
    trigger_ok = context.trigger_satisfied(trigger_id)

    warnings: list[PortfolioWarning] = []

    for target_id in effect.targets:
        # Validate target reference
        if not context.work_item_exists(target_id):
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TARGET,
                    severity=PortfolioEffectSeverity.ERROR,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "target_id": target_id,
                        "trigger_id": trigger_id,
                        "effect_type": EFFECT_TYPE,
                        "reason": "Target work item not found in dataset.",
                    },
                )
            )
            continue

        if not trigger_ok:
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.QUALITY_PREREQUISITE_RISK,
                    severity=PortfolioEffectSeverity.WARNING,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "effect_id": effect.id,
                        "trigger_work_item_id": trigger_id,
                        "target_work_item_id": target_id,
                        "trigger_completed": False,
                        "risk": "ELEVATED",
                        "quantitative_impact_known": False,
                    },
                )
            )
        else:
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.QUALITY_PREREQUISITE_SATISFIED,
                    severity=PortfolioEffectSeverity.INFO,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "effect_id": effect.id,
                        "trigger_work_item_id": trigger_id,
                        "target_work_item_id": target_id,
                        "trigger_completed": True,
                        "risk": "NORMAL",
                        "quantitative_impact_known": False,
                    },
                )
            )

    return PortfolioEffectEvaluation(
        effect_id=effect.id,
        effect_type=EFFECT_TYPE,
        trigger_work_item_id=trigger_id,
        targets=list(effect.targets),
        trigger_satisfied=trigger_ok,
        deterministic=False,   # qualitative — no numeric impact at all
        applied=False,          # no numeric change made
        warnings=warnings,
    )
