"""Commercial Evaluation result models — Phase 2C.

All models are Pydantic, immutable where practical, machine-readable.
No localized strings; reason codes + evidence dicts only.

Key design principles:
    - FULL_IF_COMMITTED: committed_delivery_hours_if_won uses full hours, never
      probability-adjusted. expected_delivery_hours is separate and informational.
    - NO weighted score fields: Phase 2D adds scoring on top of these metrics.
    - Gross margin ratio is None when price_jpy == 0 (zero-safe).
    - All JPY values are float (matching domain model). Ratios are float.
    - Canonical dataset is never mutated; all derived values live here.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .reason_codes import CommercialReasonCode, CommercialSeverity


# ---------------------------------------------------------------------------
# Availability state
# ---------------------------------------------------------------------------

class OptionAvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    LOCKED = "LOCKED"        # Portfolio effect lock (Phase 2B)
    EXPIRED = "EXPIRED"      # Parent opportunity expired
    INVALID = "INVALID"      # Bad reference / invalid data


# ---------------------------------------------------------------------------
# Deliverability state
# ---------------------------------------------------------------------------

class OptionDeliverabilityStatus(str, Enum):
    INDIVIDUALLY_DELIVERABLE = "INDIVIDUALLY_DELIVERABLE"
    NOT_INDIVIDUALLY_DELIVERABLE = "NOT_INDIVIDUALLY_DELIVERABLE"
    BLOCKED = "BLOCKED"      # Parent opportunity is BLOCKED (hard dep)
    LOCKED = "LOCKED"        # Availability-derived: can't assess delivery if locked
    EXPIRED = "EXPIRED"      # Availability-derived
    INVALID = "INVALID"      # Invalid/missing commercial facts or references


# ---------------------------------------------------------------------------
# Warning / reason item
# ---------------------------------------------------------------------------

class CommercialWarning(BaseModel):
    """Structured warning emitted during commercial evaluation."""

    model_config = ConfigDict(frozen=True)

    code: CommercialReasonCode
    severity: CommercialSeverity
    option_id: str | None = None
    work_item_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Commercial metrics for a single option
# ---------------------------------------------------------------------------

class OptionMetrics(BaseModel):
    """All commercial and operational metrics for one commercial option.

    Follows FULL_IF_COMMITTED policy:
        committed_delivery_hours_if_won = full delivery_hours (never probability-reduced)
        expected_delivery_hours = delivery_hours * win_probability (informational only)

    Gross margin ratio is None when price_jpy == 0.
    No weighted score — that is Phase 2D.
    """

    model_config = ConfigDict(frozen=True)

    option_id: str
    work_item_id: str
    label: str

    # --- Availability -----------------------------------------------------------
    availability: OptionAvailabilityStatus
    availability_reason_codes: list[CommercialReasonCode] = Field(default_factory=list)

    # --- Revenue & margin -------------------------------------------------------
    price_jpy: int | float | None
    direct_cost_jpy: int | float | None
    gross_margin_jpy: int | float | None       # price - direct_cost
    gross_margin_ratio: float | None           # gross_margin / price; None if price == 0

    # --- Probability-weighted analysis ------------------------------------------
    win_probability: float | None
    expected_revenue_jpy: int | float | None  # price * probability
    expected_margin_jpy: int | float | None   # gross_margin * probability

    # --- Follow-on value --------------------------------------------------------
    follow_on_value_jpy: int | float | None
    expected_follow_on_value_jpy: int | float | None

    # --- Hours (FULL_IF_COMMITTED) ----------------------------------------------
    base_opportunity_effort_hours: float      # work_item.required_hours
    delivery_hours: float | None              # option.delivery_hours
    committed_delivery_hours_if_won: float | None
    total_committed_hours_if_won: float | None
    expected_delivery_hours: float | None

    # --- Cash timing ------------------------------------------------------------
    payment_days: int | None                  # option.payment_days (for Phase 2F)
    cash_in_days: int | None                  # work_item cash timing, preserved separately

    # --- Deliverability ---------------------------------------------------------
    deliverability: OptionDeliverabilityStatus

    # --- Flags ------------------------------------------------------------------
    selectable: bool = False

    # Machine-readable facts/explanations.  Warnings contains only notable
    # conditions; reasons includes positive states as well.
    reasons: list[CommercialWarning] = Field(default_factory=list)

    # --- Warnings ---------------------------------------------------------------
    warnings: list[CommercialWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-opportunity evaluation
# ---------------------------------------------------------------------------

class OpportunityEvaluation(BaseModel):
    """Commercial evaluation for one sales opportunity and all its options.

    MUTUALLY_EXCLUSIVE policy: at most one option may be committed.
    Phase 2C does NOT select an option — that is Phase 2D / Phase 2E.
    """

    model_config = ConfigDict(frozen=True)

    work_item_id: str
    title: str

    # Opportunity-level state
    opportunity_expired: bool
    opportunity_blocked: bool          # Hard dependency unsatisfied
    opportunity_due_date: str | None   # ISO date string
    selection_policy: str = "MUTUALLY_EXCLUSIVE"

    # All options (metrics computed even for LOCKED options, for explanation)
    options: list[OptionMetrics] = Field(default_factory=list)

    # Opportunity-level warnings
    warnings: list[CommercialWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------

class CommercialEvaluationResult(BaseModel):
    """Top-level result from the Commercial Evaluation Engine (Phase 2C).

    Contains a structured evaluation of every sales opportunity and its options.

    Phase 2C is DESCRIPTIVE — it answers "what does each option look like?",
    not "which option should be selected?".

    Final option selection requires Phase 2D (scoring) and Phase 2E (planner).
    """

    model_config = ConfigDict(frozen=True)

    # One entry per sales opportunity in the dataset
    opportunities: list[OpportunityEvaluation] = Field(default_factory=list)

    # Flattened warnings for quick access
    warnings: list[CommercialWarning] = Field(default_factory=list)

    def get_opportunity(self, work_item_id: str) -> OpportunityEvaluation | None:
        """Look up an opportunity evaluation by work_item_id."""
        return next(
            (o for o in self.opportunities if o.work_item_id == work_item_id),
            None,
        )

    def get_option(self, option_id: str) -> OptionMetrics | None:
        """Look up option metrics by option_id across all opportunities."""
        for opp in self.opportunities:
            for opt in opp.options:
                if opt.option_id == option_id:
                    return opt
        return None

    def get_available_options(self, work_item_id: str) -> list[OptionMetrics]:
        """Return only AVAILABLE options for an opportunity."""
        opp = self.get_opportunity(work_item_id)
        if opp is None:
            return []
        return [o for o in opp.options if o.availability == OptionAvailabilityStatus.AVAILABLE]
