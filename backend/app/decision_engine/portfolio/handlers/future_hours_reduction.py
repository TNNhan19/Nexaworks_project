"""Handler for effect.type == 'future_hours_reduction'.

Business rule (approved V1):
    - PROBABILISTIC effect
    - No random sampling — deterministic evaluation of both scenarios
    - expected_impact_fraction = probability * impact_fraction
    - SUCCESS scenario: effective_hours = base * (1 - impact_fraction)
    - DOWNSIDE scenario: effective_hours = base (unchanged)
    - The committed operational plan must NOT assume the expected reduction
    - Always derived from canonical base hours (idempotent)

Key distinction:
    EXPECTED BUSINESS VALUE  !=  GUARANTEED OPERATIONAL CAPACITY
"""
from __future__ import annotations

from app.domain.models import PortfolioEffect

from ..context import PortfolioEvaluationContext
from ..models import (
    PortfolioEffectEvaluation,
    PortfolioWarning,
    ProbabilisticHoursImpact,
)
from ..reason_codes import PortfolioEffectCode, PortfolioEffectSeverity

EFFECT_TYPE = "future_hours_reduction"


def handle_future_hours_reduction(
    effect: PortfolioEffect,
    context: PortfolioEvaluationContext,
    base_hours_map: dict[str, float],
) -> tuple[PortfolioEffectEvaluation, dict[str, ProbabilisticHoursImpact]]:
    """Evaluate a probabilistic future_hours_reduction effect.

    Parameters
    ----------
    effect:
        The PortfolioEffect with type 'future_hours_reduction'.
    context:
        Evaluation context with trigger/completion state.
    base_hours_map:
        Mapping work_item_id → canonical required_hours.

    Returns
    -------
    evaluation:
        Full PortfolioEffectEvaluation record.
    impacts:
        Mapping target_id → ProbabilisticHoursImpact.
        Populated regardless of whether the trigger is satisfied or not
        (downside_case always equals base in both situations).
    """
    trigger_id = effect.trigger
    trigger_ok = context.trigger_satisfied(trigger_id)
    impact_fraction: float = effect.effect.get("value", 0.0)
    probability: float = effect.effect.get("probability", 0.0)
    expected_impact_fraction = probability * impact_fraction

    warnings: list[PortfolioWarning] = []
    impacts: dict[str, ProbabilisticHoursImpact] = {}

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
            # Trigger eligible — both scenarios modelled; outcome not yet realized
            success_hours = base_hours * (1.0 - impact_fraction)
            impact = ProbabilisticHoursImpact(
                base_required_hours=base_hours,
                probability=probability,
                impact_fraction=impact_fraction,
                expected_impact_fraction=expected_impact_fraction,
                success_case_hours=success_hours,
                downside_case_hours=base_hours,
            )
            impacts[target_id] = impact
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.FUTURE_HOURS_REDUCTION_POSSIBLE,
                    severity=PortfolioEffectSeverity.INFO,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "base_required_hours": base_hours,
                        "probability": probability,
                        "impact_fraction": impact_fraction,
                        "expected_impact_fraction": expected_impact_fraction,
                        "success_case_hours": success_hours,
                        "downside_case_hours": base_hours,
                        "note": (
                            "Operational plan must NOT assume expected reduction. "
                            "Both scenarios preserved separately."
                        ),
                    },
                )
            )
        else:
            # Trigger not satisfied — no impact at all; both scenarios = base
            impact = ProbabilisticHoursImpact(
                base_required_hours=base_hours,
                probability=probability,
                impact_fraction=impact_fraction,
                expected_impact_fraction=expected_impact_fraction,
                success_case_hours=base_hours,
                downside_case_hours=base_hours,
            )
            impacts[target_id] = impact
            warnings.append(
                PortfolioWarning(
                    code=PortfolioEffectCode.FUTURE_HOURS_REDUCTION_TRIGGER_NOT_SATISFIED,
                    severity=PortfolioEffectSeverity.INFO,
                    effect_id=effect.id,
                    target_id=target_id,
                    details={
                        "base_required_hours": base_hours,
                        "trigger_work_item_id": trigger_id,
                        "trigger_satisfied": False,
                        "note": "Both scenarios equal base hours; no impact applicable.",
                    },
                )
            )

    evaluation = PortfolioEffectEvaluation(
        effect_id=effect.id,
        effect_type=EFFECT_TYPE,
        trigger_work_item_id=trigger_id,
        targets=list(effect.targets),
        trigger_satisfied=trigger_ok,
        deterministic=False,
        applied=trigger_ok,
        probabilistic_hours_impacts=impacts,
        warnings=warnings,
    )
    return evaluation, impacts
