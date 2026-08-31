"""Handler for effect.type == 'cash_inflow'.

Business rule (approved V1):
    - PROBABILISTIC effect
    - No random sampling — deterministic evaluation of all scenarios
    - Separate values:
        expected  = probability × cash_inflow_jpy
        success   = cash_inflow_jpy (full amount if realized)
        downside  = 0 (no cash if collection fails)
    - Do NOT add expected value to committed cash and call the plan safe
    - The Cash-flow Simulator (Phase 2F) handles timeline / buffer simulation
    - Phase 2B only prepares the structured effect metadata
    - Target 'company_cash' is a special sentinel (not a work item ID)
"""
from __future__ import annotations

from app.domain.models import PortfolioEffect

from ..context import PortfolioEvaluationContext
from ..models import (
    CashEffect,
    PortfolioEffectEvaluation,
    PortfolioWarning,
)
from ..reason_codes import PortfolioEffectCode, PortfolioEffectSeverity

EFFECT_TYPE = "cash_inflow"

# Special sentinel used in the schema to indicate company-level cash impact
# rather than a specific work item target.
COMPANY_CASH_SENTINEL = "company_cash"


def handle_cash_inflow(
    effect: PortfolioEffect,
    context: PortfolioEvaluationContext,
) -> tuple[PortfolioEffectEvaluation, CashEffect | None]:
    """Evaluate a probabilistic cash_inflow effect.

    Parameters
    ----------
    effect:
        The PortfolioEffect with type 'cash_inflow'.
    context:
        Evaluation context with trigger state.

    Returns
    -------
    evaluation:
        Full PortfolioEffectEvaluation record.
    cash_effect:
        Populated CashEffect if trigger is in the dataset (even if not satisfied),
        None only if the effect is malformed.
    """
    trigger_id = effect.trigger
    trigger_ok = context.trigger_satisfied(trigger_id)
    cash_inflow_jpy: float = effect.effect.get("value_jpy", 0.0)
    probability: float = effect.effect.get("probability", 0.0)

    warnings: list[PortfolioWarning] = []

    # The trigger must be a valid work item
    if not context.work_item_exists(trigger_id):
        warnings.append(
            PortfolioWarning(
                code=PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TRIGGER,
                severity=PortfolioEffectSeverity.ERROR,
                effect_id=effect.id,
                target_id=None,
                details={
                    "trigger_id": trigger_id,
                    "effect_type": EFFECT_TYPE,
                    "reason": "Trigger work item not found in dataset.",
                },
            )
        )
        evaluation = PortfolioEffectEvaluation(
            effect_id=effect.id,
            effect_type=EFFECT_TYPE,
            trigger_work_item_id=trigger_id,
            targets=list(effect.targets),
            trigger_satisfied=False,
            deterministic=False,
            applied=False,
            warnings=warnings,
        )
        return evaluation, None

    expected_jpy = probability * cash_inflow_jpy

    if trigger_ok:
        code = PortfolioEffectCode.PROBABILISTIC_CASH_INFLOW
        severity = PortfolioEffectSeverity.INFO
    else:
        code = PortfolioEffectCode.CASH_INFLOW_TRIGGER_NOT_SATISFIED
        severity = PortfolioEffectSeverity.INFO
        # When trigger not satisfied: effective cash in all scenarios = 0
        cash_inflow_jpy = 0.0
        expected_jpy = 0.0
        probability = 0.0

    cash_effect = CashEffect(
        effect_id=effect.id,
        trigger_work_item_id=trigger_id,
        trigger_satisfied=trigger_ok,
        probability=probability,
        cash_inflow_jpy=effect.effect.get("value_jpy", 0.0),  # Always preserve declared amount
        expected_cash_inflow_jpy=expected_jpy,
        success_case_cash_inflow_jpy=effect.effect.get("value_jpy", 0.0) if trigger_ok else 0.0,
        downside_case_cash_inflow_jpy=0.0,
    )

    warnings.append(
        PortfolioWarning(
            code=code,
            severity=severity,
            effect_id=effect.id,
            target_id=None,
            details={
                "trigger_work_item_id": trigger_id,
                "trigger_satisfied": trigger_ok,
                "probability": cash_effect.probability,
                "cash_inflow_jpy": cash_effect.cash_inflow_jpy,
                "expected_cash_inflow_jpy": cash_effect.expected_cash_inflow_jpy,
                "success_case_cash_inflow_jpy": cash_effect.success_case_cash_inflow_jpy,
                "downside_case_cash_inflow_jpy": 0,
                "note": (
                    "Phase 2B only. Cash-flow buffer simulation belongs to Phase 2F."
                ),
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
        cash_effect=cash_effect,
        warnings=warnings,
    )
    return evaluation, cash_effect
