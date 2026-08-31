"""Portfolio Effects result models.

All models are Pydantic, immutable (frozen where practical), and machine-readable.
No localized strings are stored here; use reason codes + evidence dicts.

Design:
    Each evaluated effect produces a PortfolioEffectEvaluation.
    The top-level PortfolioEffectsResult aggregates all evaluations plus
    derived indexes for convenient downstream consumption.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .reason_codes import PortfolioEffectCode, PortfolioEffectSeverity


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

class PortfolioWarning(BaseModel):
    """A structured warning emitted by an effect handler."""

    model_config = ConfigDict(frozen=True)

    code: PortfolioEffectCode
    severity: PortfolioEffectSeverity
    effect_id: str
    target_id: str | None = None  # None for effect-level (not target-specific) warnings
    details: dict[str, Any] = Field(default_factory=dict)


class AppliedReduction(BaseModel):
    """Evidence record for one reduction contribution inside an HoursOverride."""

    model_config = ConfigDict(frozen=True)

    effect_id: str
    trigger_work_item_id: str
    reduction_fraction: float


class HoursOverride(BaseModel):
    """Deterministic hours override produced by hours_reduction effect(s).

    When a single effect targets a work item: applied_reductions has one entry.
    When multiple active effects target the same item (collision), they are
    combined via MULTIPLICATIVE_COMPOUNDING (V1 assumption — see AssumptionRegistry)
    and applied_reductions lists each contributing reduction for full traceability.

    The calculation is ALWAYS derived from base_required_hours, never stacked
    on a previously mutated value.
    """

    model_config = ConfigDict(frozen=True)

    base_required_hours: float
    effective_required_hours: float
    reduction_fraction: float        # net combined fraction: 1 - product(1 - ri)
    applied: bool                    # True only when at least one trigger was satisfied
    applied_reductions: list[AppliedReduction] = Field(default_factory=list)
    """Ordered list of reduction contributions (for traceability, not order-dependent)."""


class ProbabilisticHoursImpact(BaseModel):
    """Probabilistic hours impact produced by a future_hours_reduction effect."""

    model_config = ConfigDict(frozen=True)

    base_required_hours: float
    probability: float
    impact_fraction: float
    expected_impact_fraction: float  # probability * impact_fraction

    # Operational scenarios — always derived from base (never stacked)
    success_case_hours: float        # base * (1 - impact_fraction)
    downside_case_hours: float       # base (unchanged)


class CommercialOptionState(BaseModel):
    """Availability state of a commercial option after portfolio evaluation."""

    model_config = ConfigDict(frozen=True)

    option_id: str
    available: bool
    reason_codes: list[PortfolioEffectCode] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class CashEffect(BaseModel):
    """Probabilistic cash inflow effect."""

    model_config = ConfigDict(frozen=True)

    effect_id: str
    trigger_work_item_id: str
    trigger_satisfied: bool
    probability: float
    cash_inflow_jpy: float             # Full amount if realized
    expected_cash_inflow_jpy: float    # probability * cash_inflow_jpy
    success_case_cash_inflow_jpy: float   # = cash_inflow_jpy
    downside_case_cash_inflow_jpy: float  # = 0


# ---------------------------------------------------------------------------
# Per-effect evaluation result
# ---------------------------------------------------------------------------

class PortfolioEffectEvaluation(BaseModel):
    """Full evaluation record for a single declared portfolio effect.

    Contains all fields needed for traceability:
    - what the effect is
    - whether it triggered
    - what it changed (if anything)
    - warnings or validation errors
    - whether it was deterministic or probabilistic
    """

    model_config = ConfigDict(frozen=True)

    effect_id: str
    effect_type: str
    trigger_work_item_id: str
    targets: list[str]
    trigger_satisfied: bool
    deterministic: bool           # True = deterministic, False = probabilistic
    applied: bool                 # For deterministic: was reduction applied?
                                  # For probabilistic: trigger was eligible
    warnings: list[PortfolioWarning] = Field(default_factory=list)

    # Type-specific derived results (only the relevant one will be populated)
    hours_override: HoursOverride | None = None                    # E002 targets
    probabilistic_hours_impacts: dict[str, ProbabilisticHoursImpact] = Field(
        default_factory=dict
    )                                                              # E003: target_id → impact
    option_states: list[CommercialOptionState] = Field(default_factory=list)  # E004
    cash_effect: CashEffect | None = None                          # E005


# ---------------------------------------------------------------------------
# Work item derived state (aggregated across all effects)
# ---------------------------------------------------------------------------

class DerivedWorkItemState(BaseModel):
    """Aggregated effective state for a single work item after all effects.

    - effective_required_hours: hours to use for feasibility/planning.
      Equals base hours unless a deterministic hours_reduction was applied.
    - probabilistic_hours_scenarios: if a probabilistic effect targets this item,
      the success and downside cases are preserved here.
    - portfolio_warnings: all portfolio warnings that reference this work item.
    """

    model_config = ConfigDict(frozen=True)

    work_item_id: str
    base_required_hours: float
    effective_required_hours: float  # = base unless deterministic reduction applied
    hours_override_applied: bool = False
    probabilistic_hours: ProbabilisticHoursImpact | None = None
    portfolio_warnings: list[PortfolioWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------

class PortfolioEffectsResult(BaseModel):
    """Top-level result from the Portfolio Effects Engine.

    The original CandidateDataset is NOT mutated.  All derived values live here.

    Downstream modules (Feasibility, Scoring, Planner) should:
    - Use ``work_item_states[wid].effective_required_hours`` for capacity/hours checks.
    - Use ``commercial_option_states[option_id].available`` for option availability.
    - Use ``cash_effects`` for cash-flow context.
    - Use ``warnings`` for qualitative risks (quality_prerequisite etc.).
    - Use ``effects`` for full traceability of what was evaluated and why.
    """

    model_config = ConfigDict(frozen=True)

    # Full per-effect evaluation records (one per declared PortfolioEffect)
    effects: list[PortfolioEffectEvaluation] = Field(default_factory=list)

    # Derived indexes — convenient for downstream consumption
    work_item_states: dict[str, DerivedWorkItemState] = Field(default_factory=dict)
    """Keyed by work_item_id.  Only work items affected by at least one effect appear."""

    commercial_option_states: dict[str, CommercialOptionState] = Field(default_factory=dict)
    """Keyed by option_id (e.g. 'W007-B')."""

    cash_effects: list[CashEffect] = Field(default_factory=list)

    warnings: list[PortfolioWarning] = Field(default_factory=list)
    """All warnings across all effects (flattened for quick access)."""

    def get_effective_hours(self, work_item_id: str, base_hours: float) -> float:
        """Return effective required hours for a work item.

        If a deterministic hours_reduction was applied, returns the reduced value.
        Otherwise returns base_hours unchanged.

        Parameters
        ----------
        work_item_id:
            The work item to look up.
        base_hours:
            The canonical required_hours from the dataset (always the fallback).
        """
        state = self.work_item_states.get(work_item_id)
        if state is not None and state.hours_override_applied:
            return state.effective_required_hours
        return base_hours

    def is_option_available(self, option_id: str) -> bool:
        """Return availability of a commercial option.

        Options NOT referenced by any unlock effect are considered available by default.
        Only explicitly LOCKED options return False.
        """
        state = self.commercial_option_states.get(option_id)
        if state is None:
            return True  # Not subject to any unlock condition
        return state.available
