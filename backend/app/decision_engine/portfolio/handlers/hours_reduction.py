"""Handler for effect.type == 'hours_reduction'.

Business rule (approved V1):
    - DETERMINISTIC effect
    - When trigger is satisfied:
        effective_hours = base_hours * (1 - reduction_fraction)
    - Always derived from the CANONICAL base value, never stacked.
    - Idempotent: running twice on the same context gives the same result.
    - base_required_hours is always preserved separately.
    - Fractional hours are preserved (no silent truncation).
"""
from __future__ import annotations

from app.domain.models import PortfolioEffect

from ..context import PortfolioEvaluationContext
from ..models import (
    AppliedReduction,
    HoursOverride,
    PortfolioEffectEvaluation,
    PortfolioWarning,
)
from ..reason_codes import PortfolioEffectCode, PortfolioEffectSeverity

EFFECT_TYPE = "hours_reduction"


def handle_hours_reduction(
    effect: PortfolioEffect,
    context: PortfolioEvaluationContext,
    base_hours_map: dict[str, float],
) -> tuple[PortfolioEffectEvaluation, dict[str, HoursOverride]]:
    """Evaluate a deterministic hours_reduction effect.

    Parameters
    ----------
    effect:
        The PortfolioEffect with type 'hours_reduction'.
    context:
        Evaluation context with trigger/completion state.
    base_hours_map:
        Mapping work_item_id → canonical required_hours from the dataset.
        The handler reads from this; it NEVER writes to it.

    Returns
    -------
    evaluation:
        Full PortfolioEffectEvaluation record.
    overrides:
        Mapping target_id → HoursOverride.  Empty if trigger not satisfied.
    """
    trigger_id = effect.trigger
    trigger_ok = context.trigger_satisfied(trigger_id)
    reduction_fraction: float = effect.effect.get("value", 0.0)

    warnings: list[PortfolioWarning] = []
    overrides: dict[str, HoursOverride] = {}

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

        base_hours = base_hours_map.get(target_id)
        if base_hours is None:
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TARGET,
                    severity=PortfolioEffectSeverity.ERROR,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "target_id": target_id,
                        "reason": "Target work item has no base_hours in base_hours_map.",
                    },
                )
            )
            continue

        if trigger_ok:
            # ALWAYS derive from canonical base — never from a previously reduced value
            effective_hours = base_hours * (1.0 - reduction_fraction)
            overrides[target_id] = HoursOverride(
                base_required_hours=base_hours,
                effective_required_hours=effective_hours,
                reduction_fraction=reduction_fraction,
                applied=True,
                applied_reductions=[
                    AppliedReduction(
                        effect_id=effect.id,
                        trigger_work_item_id=trigger_id,
                        reduction_fraction=reduction_fraction,
                    )
                ],
            )
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.HOURS_REDUCTION_APPLIED,
                    severity=PortfolioEffectSeverity.INFO,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "base_required_hours": base_hours,
                        "effective_required_hours": effective_hours,
                        "reduction_fraction": reduction_fraction,
                        "trigger_work_item_id": trigger_id,
                    },
                )
            )
        else:
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.HOURS_REDUCTION_NOT_APPLIED,
                    severity=PortfolioEffectSeverity.INFO,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "base_required_hours": base_hours,
                        "effective_required_hours": base_hours,
                        "reduction_fraction": reduction_fraction,
                        "trigger_work_item_id": trigger_id,
                        "trigger_satisfied": False,
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
        applied=trigger_ok and bool(overrides),
        hours_override=overrides.get(effect.targets[0]) if len(effect.targets) == 1 else None,
        warnings=warnings,
    )
    return evaluation, overrides
