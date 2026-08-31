"""Shared fixtures for Phase 2B portfolio effect tests.

Uses synthetic minimal datasets — no reliance on canonical IDs.
All canonical-dataset tests live in test_portfolio_integration.py.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.decision_engine.portfolio import (
    PortfolioEvaluationContext,
    PortfolioEffectsEngine,
)
from app.domain.models import (
    CandidateDataset,
    CommercialOption,
    Company,
    Enumerations,
    Metadata,
    Person,
    PortfolioEffect,
    WorkItem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PLAN_START = date(2026, 10, 5)
PLAN_END = date(2026, 11, 1)


def make_metadata():
    return Metadata(
        dataset_id="TEST-PE",
        version="1.0.0",
        planning_start=PLAN_START,
        planning_end=PLAN_END,
        currency="JPY",
    )


def make_company():
    return Company(
        name="TestCo",
        starting_cash_jpy=10_000_000,
        fixed_cash_outflow_jpy=5_000_000,
        minimum_cash_buffer_jpy=2_000_000,
    )


def make_person(pid: str = "PX", capacity: float = 100.0):
    return Person(
        id=pid, name=f"Person {pid}",
        capacity_hours=capacity, skills={}, languages=[],
    )


def make_work_item(wid: str, hours: float = 50.0):
    return WorkItem(
        id=wid, title=f"Work {wid}", type="delivery",
        mandatory=False, required_hours=hours,
        earliest_start=PLAN_START, due_date=PLAN_END,
    )


def make_option(option_id: str, work_item_id: str):
    return CommercialOption(
        work_item_id=work_item_id, option_id=option_id,
        label=f"Option {option_id}", price_jpy=1_000_000,
        delivery_hours=50.0, estimated_win_probability=0.5,
    )


def make_portfolio_effect(
    eid: str,
    trigger: str,
    targets: list[str],
    effect_dict: dict,
) -> PortfolioEffect:
    return PortfolioEffect(id=eid, trigger=trigger, targets=targets, effect=effect_dict)


def make_dataset(
    work_items: list,
    effects: list,
    commercial_options: list | None = None,
    extra_people: list | None = None,
) -> CandidateDataset:
    people = extra_people or [make_person()]
    return CandidateDataset(
        metadata=make_metadata(),
        company=make_company(),
        people=people,
        customers=[],
        shared_resources=[],
        work_items=work_items,
        commercial_options=commercial_options or [],
        portfolio_effects=effects,
        enumerations=Enumerations(),
    )


def build_context(dataset: CandidateDataset, completed: set[str] | None = None):
    return PortfolioEffectsEngine.build_context_from_dataset(
        dataset,
        completed_work_item_ids=frozenset(completed or set()),
    )


@pytest.fixture
def engine():
    return PortfolioEffectsEngine()
