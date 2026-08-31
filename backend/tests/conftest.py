"""Shared pytest fixtures for feasibility tests.

Uses synthetic minimal datasets — no reliance on W001/P001/canonical IDs.
Fixtures use generic IDs (WX, PX, RX) so tests remain valid for any dataset
that conforms to the same schema.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.decision_engine.assumptions import AssumptionRegistry, DEFAULT_ASSUMPTIONS
from app.domain.models import (
    CandidateDataset,
    Company,
    Customer,
    Enumerations,
    Metadata,
    Person,
    PortfolioEffect,
    SharedResource,
    SkillRequirement,
    WorkItem,
)

# ---------------------------------------------------------------------------
# Planning window used across all synthetic tests
# ---------------------------------------------------------------------------
PLAN_START = date(2026, 10, 5)
PLAN_END = date(2026, 11, 1)


def make_metadata(
    planning_start: date = PLAN_START,
    planning_end: date = PLAN_END,
) -> Metadata:
    return Metadata(
        dataset_id="TEST-001",
        version="1.0.0",
        planning_start=planning_start,
        planning_end=planning_end,
        currency="JPY",
    )


def make_company() -> Company:
    return Company(
        name="TestCo",
        starting_cash_jpy=10_000_000,
        fixed_cash_outflow_jpy=5_000_000,
        minimum_cash_buffer_jpy=2_000_000,
    )


def make_person(
    pid: str,
    capacity: float,
    skills: dict[str, float] | None = None,
    languages: list[str] | None = None,
) -> Person:
    return Person(
        id=pid,
        name=f"Person {pid}",
        capacity_hours=capacity,
        skills=skills or {},
        languages=languages or [],
    )


def make_work_item(
    wid: str,
    required_hours: float,
    required_skills: list[SkillRequirement] | None = None,
    required_languages: list[str] | None = None,
    dependencies: list[str] | None = None,
    wtype: str = "delivery",
    mandatory: bool = False,
    due_date: date = PLAN_END,
    earliest_start: date = PLAN_START,
) -> WorkItem:
    return WorkItem(
        id=wid,
        title=f"Work {wid}",
        type=wtype,
        mandatory=mandatory,
        required_hours=required_hours,
        earliest_start=earliest_start,
        due_date=due_date,
        required_skills=required_skills or [],
        required_languages=required_languages or [],
        dependencies=dependencies or [],
    )


def make_dataset(
    people: list[Person],
    work_items: list[WorkItem],
    shared_resources: list[SharedResource] | None = None,
    customers: list[Customer] | None = None,
    planning_start: date = PLAN_START,
    planning_end: date = PLAN_END,
) -> CandidateDataset:
    return CandidateDataset(
        metadata=make_metadata(planning_start, planning_end),
        company=make_company(),
        people=people,
        customers=customers or [],
        shared_resources=shared_resources or [],
        work_items=work_items,
        commercial_options=[],
        portfolio_effects=[],
        enumerations=Enumerations(),
    )


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_assumptions() -> AssumptionRegistry:
    return DEFAULT_ASSUMPTIONS


@pytest.fixture
def coordinating_assumptions() -> AssumptionRegistry:
    """Assumptions that require project_management >= 3 for language coverage."""
    return AssumptionRegistry(
        language_customer_facing_skill="project_management",
        language_customer_facing_min_level=3.0,
    )
