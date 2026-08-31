from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    """Base model that keeps unknown fields for compatible future datasets."""

    model_config = ConfigDict(extra="allow")


class LocalizedText(FlexibleModel):
    ja: str | None = None
    en: str | None = None
    vi: str | None = None


class Metadata(FlexibleModel):
    dataset_id: str
    version: str
    scenario_name: LocalizedText | str | None = None
    planning_start: date
    planning_end: date
    currency: str
    canonical_language: str | None = None
    note: LocalizedText | str | None = None


class Company(FlexibleModel):
    name: str
    starting_cash_jpy: int
    fixed_cash_outflow_jpy: int
    minimum_cash_buffer_jpy: int
    risk_tolerance: str | None = None
    objective_is_not_defined: bool | None = None
    decision_context: LocalizedText | str | None = None


class DateRange(FlexibleModel):
    start: date
    end: date


class Person(FlexibleModel):
    id: str
    name: str
    role: LocalizedText | str | None = None
    capacity_hours: float = Field(ge=0)
    hourly_cost_jpy: float | None = Field(default=None, ge=0)
    skills: dict[str, float]
    languages: list[str]
    unavailable_ranges: list[DateRange] = Field(default_factory=list)


class Customer(FlexibleModel):
    id: str
    name: str
    industry: str | None = None
    strategic_value: float
    payment_reliability: float
    reference_value: float | None = None
    relationship_risk: float | None = None
    default_payment_days: int | None = None


class SharedResource(FlexibleModel):
    id: str
    name: LocalizedText | str
    capacity_hours: float = Field(ge=0)
    exclusive: bool | None = None


class SkillRequirement(FlexibleModel):
    skill: str
    min_level: float = Field(ge=0)


class ResourceRequirement(FlexibleModel):
    resource_id: str
    hours: float = Field(ge=0)


class WorkItem(FlexibleModel):
    id: str
    title: LocalizedText | str
    type: str
    status: str | None = None
    mandatory: bool
    committed: bool | None = None
    customer_id: str | None = None
    revenue_jpy: int | float = 0
    direct_cost_jpy: int | float = 0
    cash_in_days: int | None = None
    success_probability: float = Field(default=1.0, ge=0, le=1)
    required_hours: float = Field(ge=0)
    earliest_start: date
    due_date: date
    late_penalty_jpy_per_day: int | float = 0
    strategic_value: float | None = None
    required_skills: list[SkillRequirement] = Field(default_factory=list)
    required_languages: list[str] = Field(default_factory=list)
    resource_requirements: list[ResourceRequirement] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    notes: LocalizedText | str | None = None


class CommercialOption(FlexibleModel):
    work_item_id: str
    option_id: str
    label: LocalizedText | str
    # The JSON schema requires price/delivery/probability, while the remaining
    # commercial facts are optional.  Keep absent values as None so downstream
    # engines can report "not available" instead of silently manufacturing 0.
    price_jpy: int | float | None = None
    direct_cost_jpy: int | float | None = None
    delivery_hours: float | None = Field(default=None, ge=0)
    payment_days: int | None = None
    estimated_win_probability: float | None = Field(default=None, ge=0, le=1)
    warranty_months: int | None = None
    follow_on_value_jpy: int | float | None = None
    notes: LocalizedText | str | None = None
    dependencies: list[str] = Field(default_factory=list)


class PortfolioEffect(FlexibleModel):
    id: str
    trigger: str
    targets: list[str]
    effect: dict[str, Any]


class Enumerations(FlexibleModel):
    work_item_types: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class CandidateDataset(FlexibleModel):
    metadata: Metadata
    company: Company
    people: list[Person]
    customers: list[Customer]
    shared_resources: list[SharedResource]
    work_items: list[WorkItem]
    commercial_options: list[CommercialOption]
    portfolio_effects: list[PortfolioEffect]
    enumerations: Enumerations | None = None
