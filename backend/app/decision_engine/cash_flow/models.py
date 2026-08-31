"""Immutable, exact-JPY result models for Phase 2F."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .reason_codes import (
    CashDirection,
    CashEventType,
    CashReasonCode,
    CashScenario,
    CashSourceType,
    OverallCashStatus,
    ScenarioCashStatus,
)


class CashFinding(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: CashReasonCode
    source_id: str | None = None
    scenario: CashScenario | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CashEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    date: date
    source_type: CashSourceType
    source_id: str
    event_type: CashEventType
    scenario: CashScenario
    amount_jpy: int = Field(ge=0)
    direction: CashDirection
    deterministic: bool
    probability: float | None = Field(default=None, ge=0, le=1)
    timing_basis: str
    outside_horizon: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)


class DailyCashLedger(BaseModel):
    model_config = ConfigDict(frozen=True)
    date: date
    opening_cash_jpy: int
    cash_in_jpy: int
    cash_out_jpy: int
    net_change_jpy: int
    closing_cash_jpy: int
    minimum_buffer_jpy: int
    buffer_headroom_jpy: int
    buffer_breach: bool
    negative_cash: bool
    events: list[CashEvent] = Field(default_factory=list)


class CashScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario: CashScenario
    status: ScenarioCashStatus
    timeline: list[DailyCashLedger]
    in_horizon_events: list[CashEvent] = Field(default_factory=list)
    future_events: list[CashEvent] = Field(default_factory=list)
    total_cash_in_jpy: int
    total_cash_out_jpy: int
    event_totals_jpy: dict[str, int] = Field(default_factory=dict)
    minimum_cash_jpy: int
    minimum_cash_date: date
    ending_cash_jpy: int
    first_buffer_breach_date: date | None = None
    days_below_buffer: int = 0
    buffer_breach_dates: list[date] = Field(default_factory=list)
    negative_cash_dates: list[date] = Field(default_factory=list)


class CashFlowResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    overall_status: OverallCashStatus
    operational_plan_status: str
    starting_cash_jpy: int
    minimum_buffer_jpy: int
    scenarios: dict[CashScenario, CashScenarioResult]
    future_events: list[CashEvent] = Field(default_factory=list)
    reasons: list[CashFinding] = Field(default_factory=list)
    warnings: list[CashFinding] = Field(default_factory=list)
    assumptions_used: dict[str, Any] = Field(default_factory=dict)

    def get_scenario(self, scenario: CashScenario | str) -> CashScenarioResult:
        key = scenario if isinstance(scenario, CashScenario) else CashScenario(scenario)
        return self.scenarios[key]
