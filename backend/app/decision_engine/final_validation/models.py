"""Immutable Pydantic result models for Phase 2G Final Validation + Explanation.

All models carry only machine-readable codes and evidence dictionaries.
No natural-language strings are stored here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .reason_codes import (
    ExplanationCode,
    FindingSeverity,
    FinancialStatus,
    OperationalStatus,
    OverallStatus,
    SourcePhase,
)


# ---------------------------------------------------------------------------
# Low-level building block
# ---------------------------------------------------------------------------

class ExplanationRecord(BaseModel):
    """A single structured explanation / validation finding.

    Frontend i18n maps ``code`` to a translated message template and fills
    in ``evidence`` for interpolation.  No user-facing prose lives here.
    """

    model_config = ConfigDict(frozen=True)

    code: ExplanationCode
    severity: FindingSeverity
    source_phase: SourcePhase
    source_id: str | None = None
    """Work item ID, option ID, person ID, resource ID, or effect ID."""

    action_id: str | None = None
    """Planner action ID when different from source_id."""

    evidence: dict[str, Any] = Field(default_factory=dict)
    """Machine-readable supporting data for this finding."""


# ---------------------------------------------------------------------------
# Per-decision explanation
# ---------------------------------------------------------------------------

class DecisionExplanation(BaseModel):
    """Structured explanation for a single plan decision."""

    model_config = ConfigDict(frozen=True)

    work_item_id: str
    action_id: str
    decision: str
    """Value of DecisionType enum — kept as str to avoid coupling."""

    reason_codes: list[str] = Field(default_factory=list)
    """Planner-emitted reason codes forwarded verbatim."""

    findings: list[ExplanationRecord] = Field(default_factory=list)
    """Phase 2G validation findings for this specific decision."""

    details: dict[str, Any] = Field(default_factory=dict)
    """Forwarded from PlanDecision.details (dates, hours, scores, etc.)."""


# ---------------------------------------------------------------------------
# Mandatory summary
# ---------------------------------------------------------------------------

class MandatoryItemOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)
    work_item_id: str
    scheduled: bool
    infeasible: bool
    """True when planner explicitly marked MANDATORY_INFEASIBLE."""
    omitted: bool
    """True when item is mandatory but appears in neither selected nor infeasible."""
    prerequisite_ids: list[str] = Field(default_factory=list)
    completion_date: date | None = None


class MandatorySummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_mandatory: int
    scheduled_count: int
    infeasible_count: int
    omitted_count: int
    outcomes: list[MandatoryItemOutcome] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Capacity summary
# ---------------------------------------------------------------------------

class PersonCapacitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    person_id: str
    capacity_hours: float
    used_hours: float
    remaining_hours: float
    utilisation_pct: float
    """used_hours / capacity_hours * 100, capped at 0–100 for display."""


class CapacitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_capacity_hours: float
    total_used_hours: float
    total_remaining_hours: float
    people: list[PersonCapacitySummary] = Field(default_factory=list)
    violations: list[ExplanationRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Resource summary
# ---------------------------------------------------------------------------

class ResourceUsageSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    resource_id: str
    capacity_hours: float
    used_hours: float
    remaining_hours: float
    exclusive: bool
    utilisation_pct: float


class ResourceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    resources: list[ResourceUsageSummary] = Field(default_factory=list)
    violations: list[ExplanationRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cash summary
# ---------------------------------------------------------------------------

class ScenarioCashSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario: str
    status: str
    ending_cash_jpy: int
    minimum_cash_jpy: int
    minimum_cash_date: date
    first_buffer_breach_date: date | None = None
    days_below_buffer: int = 0
    negative_cash: bool = False


class FutureReceiptSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_id: str
    event_type: str
    date: date
    expected_amount_jpy: int
    """Amount in the EXPECTED scenario; 0 if scenario not present."""


class CashSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    starting_cash_jpy: int
    minimum_buffer_jpy: int
    financial_status: FinancialStatus
    scenarios: list[ScenarioCashSummary] = Field(default_factory=list)
    future_receipts: list[FutureReceiptSummary] = Field(default_factory=list)
    findings: list[ExplanationRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Executive summary (machine-readable, frontend renders)
# ---------------------------------------------------------------------------

class ExecutiveSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_status: str
    operational_status: str
    financial_status: str

    selected_count: int
    delayed_count: int
    no_bid_count: int
    mandatory_total: int
    mandatory_scheduled_count: int
    mandatory_infeasible_count: int

    total_capacity_hours: float
    total_used_hours: float
    total_remaining_hours: float

    expected_ending_cash_jpy: int | None = None
    downside_ending_cash_jpy: int | None = None
    success_ending_cash_jpy: int | None = None
    minimum_cash_jpy: int | None = None
    minimum_cash_date: date | None = None
    first_buffer_breach_date: date | None = None

    major_risks: list[str] = Field(default_factory=list)
    """List of ExplanationCode values (strings) for the most important risks."""

    major_strengths: list[str] = Field(default_factory=list)
    """List of ExplanationCode values (strings) for the most important positives."""


# ---------------------------------------------------------------------------
# Top-level final decision result
# ---------------------------------------------------------------------------

class FinalDecisionResult(BaseModel):
    """Complete Phase 2G result.

    Combines PlanResult (2E) + CashFlowResult (2F) into a unified,
    structured, immutable verdict with full provenance.
    """

    model_config = ConfigDict(frozen=True)

    overall_status: OverallStatus
    operational_status: OperationalStatus
    financial_status: FinancialStatus

    executive_summary: ExecutiveSummary

    mandatory_summary: MandatorySummary
    capacity_summary: CapacitySummary
    resource_summary: ResourceSummary
    cash_summary: CashSummary

    decision_explanations: list[DecisionExplanation] = Field(default_factory=list)

    validations: list[ExplanationRecord] = Field(default_factory=list)
    """Cross-cutting structural validations (dependency order, exclusivity, etc.)."""

    warnings: list[ExplanationRecord] = Field(default_factory=list)
    """Non-fatal notices forwarded from upstream phases."""

    critical_issues: list[ExplanationRecord] = Field(default_factory=list)
    """CRITICAL or ERROR severity findings that require immediate attention."""

    explanation_records: list[ExplanationRecord] = Field(default_factory=list)
    """All findings in one flat list for easy iteration."""

    source_versions: dict[str, str] = Field(default_factory=dict)
    """Phase identifiers for provenance (e.g. {'planner': '2E', 'cash': '2F'})."""

    assumptions_used: dict[str, Any] = Field(default_factory=dict)
    """Forwarded from AssumptionRegistry.model_dump()."""
