"""Portfolio Effects reason and warning codes.

All codes are machine-readable enums.
The frontend translates them into JA / EN / VI for display.
The engine never emits localized strings.
"""
from __future__ import annotations

from enum import Enum


class PortfolioEffectCode(str, Enum):
    """Reason/warning codes produced by the Portfolio Effects Engine."""

    # --- quality_prerequisite -------------------------------------------------
    QUALITY_PREREQUISITE_RISK = "QUALITY_PREREQUISITE_RISK"
    """Qualitative technical-risk warning: prerequisite not yet completed.
    Does NOT create a hard dependency or BLOCKED/INFEASIBLE status.
    """

    QUALITY_PREREQUISITE_SATISFIED = "QUALITY_PREREQUISITE_SATISFIED"
    """Prerequisite completed; elevated risk no longer active."""

    # --- hours_reduction (deterministic) --------------------------------------
    HOURS_REDUCTION_APPLIED = "HOURS_REDUCTION_APPLIED"
    """Deterministic hours reduction was applied (trigger satisfied)."""

    HOURS_REDUCTION_NOT_APPLIED = "HOURS_REDUCTION_NOT_APPLIED"
    """Trigger not satisfied; base required_hours unchanged."""

    HOURS_REDUCTION_COLLISION_COMPOUNDED = "HOURS_REDUCTION_COLLISION_COMPOUNDED"
    """Multiple active hours_reduction effects target the same work item.
    Combined using MULTIPLICATIVE_COMPOUNDING policy (V1 assumption):
        effective = base * (1 - r1) * (1 - r2) * ...
    Evidence shows each contributing reduction fraction and effect ID.
    """

    # --- future_hours_reduction (probabilistic) --------------------------------
    FUTURE_HOURS_REDUCTION_POSSIBLE = "FUTURE_HOURS_REDUCTION_POSSIBLE"
    """Probabilistic: trigger eligible but outcome not yet realized.
    Two scenarios (success / downside) are both preserved.
    """

    FUTURE_HOURS_REDUCTION_TRIGGER_NOT_SATISFIED = (
        "FUTURE_HOURS_REDUCTION_TRIGGER_NOT_SATISFIED"
    )
    """Probabilistic trigger not satisfied; both scenarios equal base hours."""

    # --- commercial_option_unlock ----------------------------------------------
    COMMERCIAL_OPTION_LOCKED = "COMMERCIAL_OPTION_LOCKED"
    """Commercial option is unavailable because the unlock trigger is not satisfied."""

    COMMERCIAL_OPTION_UNLOCKED = "COMMERCIAL_OPTION_UNLOCKED"
    """Commercial option became available because the unlock trigger is satisfied."""

    # --- cash_inflow (probabilistic) ------------------------------------------
    PROBABILISTIC_CASH_INFLOW = "PROBABILISTIC_CASH_INFLOW"
    """Probabilistic cash inflow: trigger eligible but outcome not yet realized.
    Expected, success, and downside values are all separately preserved.
    """

    CASH_INFLOW_TRIGGER_NOT_SATISFIED = "CASH_INFLOW_TRIGGER_NOT_SATISFIED"
    """Trigger not satisfied; cash inflow is zero across all scenarios."""

    # --- Validation / error ---------------------------------------------------
    PORTFOLIO_EFFECT_TRIGGER_NOT_SATISFIED = (
        "PORTFOLIO_EFFECT_TRIGGER_NOT_SATISFIED"
    )
    """Generic: trigger work item not in completed_ids (informational)."""

    INVALID_PORTFOLIO_EFFECT_TARGET = "INVALID_PORTFOLIO_EFFECT_TARGET"
    """A target ID referenced by a portfolio effect does not exist in the dataset."""

    INVALID_PORTFOLIO_EFFECT_TRIGGER = "INVALID_PORTFOLIO_EFFECT_TRIGGER"
    """The trigger work item referenced by the effect does not exist in the dataset."""

    UNSUPPORTED_PORTFOLIO_EFFECT_TYPE = "UNSUPPORTED_PORTFOLIO_EFFECT_TYPE"
    """The effect.type value is not recognised by this version of the engine."""


class PortfolioEffectSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
