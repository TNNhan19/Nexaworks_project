from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UnavailableRangeOverride(StrictModel):
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self):
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self


class CompanyOverride(StrictModel):
    starting_cash_jpy: int | None = Field(default=None, ge=0)
    fixed_cash_outflow_jpy: int | None = Field(default=None, ge=0)
    minimum_cash_buffer_jpy: int | None = Field(default=None, ge=0)


class PersonOverride(StrictModel):
    person_id: str
    capacity_hours: float | None = Field(default=None, ge=0)
    unavailable_ranges: list[UnavailableRangeOverride] | None = None


class WorkItemOverride(StrictModel):
    work_item_id: str
    required_hours: float | None = Field(default=None, ge=0)
    earliest_start: date | None = None
    due_date: date | None = None
    direct_cost_jpy: int | float | None = Field(default=None, ge=0)
    revenue_jpy: int | float | None = Field(default=None, ge=0)
    cash_in_days: int | None = Field(default=None, ge=0)
    success_probability: float | None = Field(default=None, ge=0, le=1)
    dependencies: list[str] | None = None


class CommercialOptionOverride(StrictModel):
    option_id: str
    price_jpy: int | float | None = Field(default=None, ge=0)
    direct_cost_jpy: int | float | None = Field(default=None, ge=0)
    delivery_hours: float | None = Field(default=None, ge=0)
    payment_days: int | None = Field(default=None, ge=0)
    estimated_win_probability: float | None = Field(default=None, ge=0, le=1)
    dependencies: list[str] | None = None


class ResourceOverride(StrictModel):
    resource_id: str
    capacity_hours: float | None = Field(default=None, ge=0)
    exclusive: bool | None = None


class ScenarioOverrides(StrictModel):
    company: CompanyOverride | None = None
    people: list[PersonOverride] = Field(default_factory=list)
    work_items: list[WorkItemOverride] = Field(default_factory=list)
    commercial_options: list[CommercialOptionOverride] = Field(default_factory=list)
    resources: list[ResourceOverride] = Field(default_factory=list)
    deferred_work_item_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_targets(self):
        groups = (
            ("person", [item.person_id for item in self.people]),
            ("work item", [item.work_item_id for item in self.work_items]),
            ("commercial option", [item.option_id for item in self.commercial_options]),
            ("resource", [item.resource_id for item in self.resources]),
        )
        for label, values in groups:
            duplicates = sorted({value for value in values if values.count(value) > 1})
            if duplicates:
                raise ValueError(f"duplicate {label} override targets: {duplicates}")
        deferred_duplicates = sorted({
            value for value in self.deferred_work_item_ids
            if self.deferred_work_item_ids.count(value) > 1
        })
        if deferred_duplicates:
            raise ValueError(f"duplicate deferred work item IDs: {deferred_duplicates}")
        return self


class ScenarioCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    overrides: ScenarioOverrides = Field(default_factory=ScenarioOverrides)
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"


class ScenarioPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    overrides: ScenarioOverrides | None = None
    status: Literal["ACTIVE", "INACTIVE"] | None = None


class Scenario(StrictModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    overrides: ScenarioOverrides
    status: Literal["ACTIVE", "INACTIVE"]


class ScenarioRun(StrictModel):
    run_id: str
    scenario_id: str
    timestamp: datetime
    effective_input: dict[str, Any]
    assumptions: dict[str, Any]
    feasibility: list[dict[str, Any]] = Field(default_factory=list)
    portfolio: dict[str, Any] = Field(default_factory=dict)
    commercial: dict[str, Any] = Field(default_factory=dict)
    scoring: dict[str, Any] = Field(default_factory=dict)
    plan: dict[str, Any] = Field(default_factory=dict)
    cash_flow: dict[str, Any] = Field(default_factory=dict)
    final_decision: dict[str, Any] = Field(default_factory=dict)
    status: Literal["COMPLETED", "FAILED"]
    error: dict[str, Any] | None = None


class RunComparison(StrictModel):
    run_a_id: str
    run_b_id: str
    status_transition: dict[str, dict[str, str]]
    selected: dict[str, list[str]]
    delayed: dict[str, list[str]]
    no_bid: dict[str, list[str]]
    capacity: dict[str, dict[str, float]]
    cash: dict[str, dict[str, int | None]]
    buffer_breach: dict[str, bool | str]
    major_risks: dict[str, list[str]]
    major_strengths: dict[str, list[str]]
