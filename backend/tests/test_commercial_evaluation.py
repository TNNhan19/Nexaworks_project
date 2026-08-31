"""Focused Phase 2C commercial facts, validation, and canonical regression tests."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.decision_engine.commercial import (
    CommercialEvaluationEngine,
    CommercialReasonCode,
    OptionAvailabilityStatus,
    OptionDeliverabilityStatus,
)
from app.domain.models import CommercialOption
from app.services.dataset_loader import load_dataset
from fastapi.testclient import TestClient
from app.main import app
from conftest import PLAN_START, make_dataset, make_person, make_work_item


def option(
    option_id: str = "WX-A",
    *,
    work_item_id: str = "WX",
    price: float | None = 1_000,
    cost: float | None = 400,
    hours: float | None = 20,
    probability: float | None = 0.5,
    follow_on: float | None = 200,
    dependencies: list[str] | None = None,
) -> CommercialOption:
    return CommercialOption(
        work_item_id=work_item_id,
        option_id=option_id,
        label=option_id,
        price_jpy=price,
        direct_cost_jpy=cost,
        delivery_hours=hours,
        estimated_win_probability=probability,
        follow_on_value_jpy=follow_on,
        payment_days=30,
        dependencies=dependencies or [],
    )


def evaluate(options: list[CommercialOption], *, capacity: float = 200, work_item=None, completed=frozenset()):
    work_item = work_item or make_work_item("WX", 10, wtype="sales_opportunity")
    dataset = make_dataset([make_person("PX", capacity)], [work_item])
    dataset = dataset.model_copy(update={"commercial_options": options})
    engine = CommercialEvaluationEngine()
    portfolio = engine.build_portfolio_context(dataset, completed)
    return engine.evaluate(dataset, portfolio, completed_ids=completed)


def first(result):
    return result.opportunities[0].options[0]


def test_gross_margin_ratio_and_expected_values() -> None:
    metric = first(evaluate([option(price=1_000, cost=400, probability=0.5, follow_on=200)]))
    assert metric.gross_margin_jpy == 600
    assert metric.gross_margin_ratio == pytest.approx(0.6)
    assert metric.expected_revenue_jpy == 500
    assert metric.expected_margin_jpy == 300
    assert metric.expected_follow_on_value_jpy == 100


@pytest.mark.parametrize(
    ("probability", "expected_revenue"),
    [(0.0, 0), (1.0, 1_000)],
)
def test_probability_boundaries(probability: float, expected_revenue: int) -> None:
    metric = first(evaluate([option(probability=probability)]))
    assert metric.expected_revenue_jpy == expected_revenue


def test_invalid_probability_is_structured_and_not_clamped() -> None:
    values = option().model_dump()
    values["estimated_win_probability"] = 1.2
    bad = CommercialOption.model_construct(**values)
    metric = first(evaluate([bad]))
    assert metric.availability == OptionAvailabilityStatus.INVALID
    assert metric.expected_revenue_jpy is None
    assert CommercialReasonCode.INVALID_WIN_PROBABILITY in [w.code for w in metric.warnings]


def test_zero_price_is_safe() -> None:
    metric = first(evaluate([option(price=0, cost=100)]))
    assert metric.gross_margin_jpy == -100
    assert metric.gross_margin_ratio is None
    assert CommercialReasonCode.ZERO_PRICE_OPTION in [r.code for r in metric.reasons]


def test_full_if_committed_keeps_expected_and_operational_hours_separate() -> None:
    metric = first(evaluate([option(hours=150, probability=0.72)], capacity=500))
    assert metric.delivery_hours == 150
    assert metric.committed_delivery_hours_if_won == 150
    assert metric.expected_delivery_hours == pytest.approx(108)
    assert metric.total_committed_hours_if_won == 160


def test_individually_deliverable_and_non_deliverable() -> None:
    deliverable = first(evaluate([option(hours=20)], capacity=100))
    impossible = first(evaluate([option(hours=100)], capacity=100))
    assert deliverable.deliverability == OptionDeliverabilityStatus.INDIVIDUALLY_DELIVERABLE
    assert impossible.deliverability == OptionDeliverabilityStatus.NOT_INDIVIDUALLY_DELIVERABLE


def test_option_dependency_reuses_blocked_semantics() -> None:
    prerequisite = make_work_item("PRE", 5)
    work = make_work_item("WX", 10, wtype="sales_opportunity")
    dataset = make_dataset([make_person("PX", 200)], [prerequisite, work])
    dataset = dataset.model_copy(update={"commercial_options": [option(dependencies=["PRE"])]})
    engine = CommercialEvaluationEngine()
    result = engine.evaluate(dataset, engine.build_portfolio_context(dataset))
    assert first(result).deliverability == OptionDeliverabilityStatus.BLOCKED


def test_expired_sales_opportunity_is_not_selectable() -> None:
    expired = make_work_item(
        "WX", 10, wtype="sales_opportunity", earliest_start=date(2026, 9, 1), due_date=date(2026, 10, 4)
    )
    metric = first(evaluate([option()], work_item=expired))
    assert metric.availability == OptionAvailabilityStatus.EXPIRED
    assert metric.deliverability == OptionDeliverabilityStatus.EXPIRED
    assert metric.selectable is False


def test_mutually_exclusive_group_contains_only_canonical_options() -> None:
    result = evaluate([option("WX-A"), option("WX-B")])
    opportunity = result.opportunities[0]
    assert [m.option_id for m in opportunity.options] == ["WX-A", "WX-B"]
    assert opportunity.selection_policy == "MUTUALLY_EXCLUSIVE"
    assert "no_bid" not in opportunity.model_dump()


def test_zero_value_option_is_not_classified_as_no_bid() -> None:
    metric = first(evaluate([option("FREE-ZERO", price=0, cost=0, hours=0)]))
    assert metric.option_id == "FREE-ZERO"
    assert metric.availability == OptionAvailabilityStatus.AVAILABLE
    assert metric.deliverability == OptionDeliverabilityStatus.INDIVIDUALLY_DELIVERABLE
    assert "is_no_bid" not in metric.model_dump()


def test_unseen_free_pilot_remains_a_normal_option() -> None:
    free_pilot = option("FREE-PILOT", price=0, cost=0, hours=25, probability=0.4)
    free_pilot = free_pilot.model_copy(update={"label": "Free pilot"})
    metric = first(evaluate([free_pilot]))
    assert metric.label == "Free pilot"
    assert metric.price_jpy == 0
    assert metric.delivery_hours == 25
    assert metric.expected_revenue_jpy == 0
    assert metric.selectable is True


def test_missing_optional_and_required_fields_are_not_invented() -> None:
    missing_optional = first(evaluate([option(cost=None, follow_on=None)]))
    assert missing_optional.direct_cost_jpy is None
    assert missing_optional.gross_margin_jpy is None
    assert missing_optional.expected_margin_jpy is None
    assert missing_optional.follow_on_value_jpy is None
    missing_required = first(evaluate([option(price=None)]))
    assert missing_required.availability == OptionAvailabilityStatus.INVALID
    assert missing_required.expected_revenue_jpy is None


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("price_jpy", -1, CommercialReasonCode.NEGATIVE_PRICE),
        ("direct_cost_jpy", -1, CommercialReasonCode.NEGATIVE_COST),
        ("delivery_hours", -1, CommercialReasonCode.NEGATIVE_DELIVERY_HOURS),
    ],
)
def test_negative_values_are_invalid(field: str, value: float, code: CommercialReasonCode) -> None:
    values = option().model_dump()
    values[field] = value
    bad = CommercialOption.model_construct(**values)
    metric = first(evaluate([bad]))
    assert metric.availability == OptionAvailabilityStatus.INVALID
    assert code in [warning.code for warning in metric.warnings]


def test_duplicate_option_id_and_unknown_parent_are_structured() -> None:
    duplicate_result = evaluate([option("DUP"), option("DUP")])
    assert all(metric.availability == OptionAvailabilityStatus.INVALID for metric in duplicate_result.opportunities[0].options)
    orphan_result = evaluate([option("ORPHAN", work_item_id="UNKNOWN")])
    assert orphan_result.opportunities == []
    assert CommercialReasonCode.UNKNOWN_PARENT_OPPORTUNITY in [warning.code for warning in orphan_result.warnings]


def test_result_contains_no_weighted_score() -> None:
    payload = first(evaluate([option()])).model_dump()
    assert "score" not in payload
    assert "weighted_score" not in payload
    assert "priority_score" not in payload


@pytest.fixture(scope="module")
def canonical_result():
    root = Path(__file__).resolve().parents[2]
    dataset = load_dataset(root / "data/candidate_dataset.json", root / "data/candidate_dataset.schema.json")
    engine = CommercialEvaluationEngine()
    return dataset, engine.evaluate(dataset, engine.build_portfolio_context(dataset))


def test_canonical_w006(canonical_result) -> None:
    _, result = canonical_result
    option_a = result.get_option("W006-A")
    assert option_a.gross_margin_jpy == 2_800_000
    assert option_a.expected_revenue_jpy == 2_520_000
    assert option_a.expected_delivery_hours == pytest.approx(108)
    assert option_a.committed_delivery_hours_if_won == 150


def test_canonical_w007_b_locked_and_unlocked(canonical_result) -> None:
    dataset, result = canonical_result
    assert result.get_option("W007-B").availability == OptionAvailabilityStatus.LOCKED
    engine = CommercialEvaluationEngine()
    completed = frozenset({"W005", "W022"})
    unlocked = engine.evaluate(dataset, engine.build_portfolio_context(dataset, completed), completed_ids=completed)
    assert unlocked.get_option("W007-B").availability == OptionAvailabilityStatus.AVAILABLE
    assert unlocked.get_option("W007-B").deliverability == OptionDeliverabilityStatus.INDIVIDUALLY_DELIVERABLE


def test_canonical_w011_c_remains_an_ordinary_declared_option(canonical_result) -> None:
    _, result = canonical_result
    opportunity = result.get_opportunity("W011")
    assert opportunity is not None
    assert [item.option_id for item in opportunity.options] == ["W011-A", "W011-B", "W011-C"]
    assert "no_bid" not in opportunity.model_dump()
    assert result.get_option("W011-C").label == "No-bid"
    assert "is_no_bid" not in result.get_option("W011-C").model_dump()
    assert result.get_option("W011-B").gross_margin_jpy == 760_000


def test_canonical_w012_b_remains_an_ordinary_declared_option(canonical_result) -> None:
    _, result = canonical_result
    opportunity = result.get_opportunity("W012")
    assert opportunity is not None
    assert [item.option_id for item in opportunity.options] == ["W012-A", "W012-B"]
    assert result.get_option("W012-B").label == "Do not apply"
    assert result.get_option("W012-B").price_jpy == 0
    assert "is_no_bid" not in result.get_option("W012-B").model_dump()


def test_commercial_api_all_and_single() -> None:
    client = TestClient(app)
    all_response = client.get("/api/v1/commercial")
    assert all_response.status_code == 200
    assert len(all_response.json()["opportunities"]) == 7
    single = client.get("/api/v1/commercial/W007")
    assert single.status_code == 200
    option_b = next(item for item in single.json()["options"] if item["option_id"] == "W007-B")
    assert option_b["availability"] == "LOCKED"


def test_commercial_api_unknown_opportunity_is_404() -> None:
    assert TestClient(app).get("/api/v1/commercial/UNKNOWN").status_code == 404
