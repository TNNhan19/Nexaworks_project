"""Focused Phase 2D scoring, normalization, eligibility, and canonical tests."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.decision_engine.assumptions import AssumptionRegistry, ScoringWeights
from app.decision_engine.commercial import CommercialEvaluationEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.scoring import ActionType, ComponentName, ScoringEngine, SelectionStatus
from app.decision_engine.scoring.normalization import normalize_ecdf
from app.domain.models import CommercialOption, PortfolioEffect, SkillRequirement
from app.main import app
from app.services.dataset_loader import load_dataset
from conftest import PLAN_END, PLAN_START, make_dataset, make_person, make_work_item


def commercial_option(
    option_id="WX-A",
    *,
    work_item_id="WX",
    price=1_000,
    cost=400,
    hours=100,
    probability=0.5,
    follow_on=500,
    payment_days=27,
):
    return CommercialOption(
        work_item_id=work_item_id,
        option_id=option_id,
        label=option_id,
        price_jpy=price,
        direct_cost_jpy=cost,
        delivery_hours=hours,
        estimated_win_probability=probability,
        follow_on_value_jpy=follow_on,
        payment_days=payment_days,
    )


def run_scoring(dataset, *, completed=frozenset(), reference=None, assumptions=None):
    portfolio_engine = PortfolioEffectsEngine()
    context = portfolio_engine.build_context_from_dataset(dataset, completed)
    portfolio = portfolio_engine.evaluate(dataset, context)
    commercial = CommercialEvaluationEngine().evaluate(
        dataset, portfolio, completed_ids=completed
    )
    return ScoringEngine(assumptions or AssumptionRegistry()).evaluate(
        dataset,
        portfolio,
        commercial,
        completed_ids=completed,
        scoring_reference=reference,
    )


def simple_dataset(*, mandatory=False, revenue=1_000, cost=200, probability=1.0, hours=10):
    work = make_work_item("WX", hours, mandatory=mandatory)
    work = work.model_copy(update={
        "revenue_jpy": revenue,
        "direct_cost_jpy": cost,
        "success_probability": probability,
        "strategic_value": 3,
    })
    return make_dataset([make_person("PX", 200)], [work])


def test_balanced_weights_sum_to_one_and_negative_is_invalid() -> None:
    weights = ScoringWeights()
    assert sum(weights.model_dump().values()) == pytest.approx(1.0)
    with pytest.raises(ValidationError):
        ScoringWeights(economic_value=-0.01, strategic_customer=0.51)


def test_normalized_components_and_score_are_bounded() -> None:
    result = run_scoring(simple_dataset())
    candidate = result.candidates[0]
    assert 0 <= candidate.business_value_score <= 100
    assert all(
        component.normalized_value is None or 0 <= component.normalized_value <= 1
        for component in candidate.components
    )


def test_exact_weighted_trace_reconciles_to_score() -> None:
    candidate = run_scoring(simple_dataset()).candidates[0]
    for component in candidate.components:
        if component.applicable:
            assert component.weighted_contribution == pytest.approx(
                component.normalized_value * component.effective_weight
            )
    assert candidate.business_value_score == round(
        100 * sum(component.weighted_contribution for component in candidate.components), 2
    )


def test_jpy_is_normalized_before_weighting() -> None:
    candidate = run_scoring(simple_dataset(revenue=10_000_000)).candidates[0]
    economic = candidate.get_component(ComponentName.ECONOMIC_VALUE)
    assert economic.raw_value == 9_999_800
    assert economic.normalized_value == 1.0
    assert economic.weighted_contribution <= economic.effective_weight


def test_hard_infeasibility_is_separate_from_score() -> None:
    feasible = make_work_item("A", 10).model_copy(
        update={"revenue_jpy": 5_000, "strategic_value": 5}
    )
    infeasible = feasible.model_copy(update={
        "id": "B",
        "required_skills": [SkillRequirement(skill="missing", min_level=5)],
    })
    result = run_scoring(make_dataset([make_person("PX", 100)], [feasible, infeasible]))
    candidate = result.get_candidate("B")
    assert candidate.selection_status == SelectionStatus.INFEASIBLE
    assert candidate.eligible_for_selection is False
    assert candidate.business_value_score == result.get_candidate("A").business_value_score


def test_blocked_stays_not_selectable() -> None:
    dependency = make_work_item("PRE", 5)
    blocked = make_work_item("WX", 10, dependencies=["PRE"]).model_copy(
        update={"revenue_jpy": 10_000, "strategic_value": 5}
    )
    result = run_scoring(make_dataset([make_person("PX", 100)], [dependency, blocked]))
    assert result.get_candidate("WX").selection_status == SelectionStatus.BLOCKED
    assert result.get_candidate("WX").eligible_for_selection is False


def test_expired_and_invalid_option_states_are_preserved() -> None:
    expired_work = make_work_item(
        "EX", 10, wtype="sales_opportunity",
        earliest_start=date(2026, 9, 1), due_date=date(2026, 10, 4),
    ).model_copy(update={"strategic_value": 3})
    expired_dataset = make_dataset([make_person("PX", 200)], [expired_work]).model_copy(
        update={"commercial_options": [commercial_option("EX-A", work_item_id="EX")]}
    )
    expired = run_scoring(expired_dataset).get_candidate("EX-A")
    assert expired.selection_status == SelectionStatus.EXPIRED
    assert expired.eligible_for_selection is False

    invalid_work = make_work_item("INV", 10, wtype="sales_opportunity").model_copy(
        update={"strategic_value": 3}
    )
    invalid_option = commercial_option("INV-A", work_item_id="INV").model_copy(
        update={"price_jpy": None}
    )
    invalid_dataset = make_dataset([make_person("PX", 200)], [invalid_work]).model_copy(
        update={"commercial_options": [invalid_option]}
    )
    invalid = run_scoring(invalid_dataset).get_candidate("INV-A")
    assert invalid.selection_status == SelectionStatus.INVALID
    assert invalid.eligible_for_selection is False


def test_mandatory_does_not_change_business_score() -> None:
    first = make_work_item("A", 10, mandatory=False).model_copy(
        update={"revenue_jpy": 1_000, "direct_cost_jpy": 200, "strategic_value": 3}
    )
    second = first.model_copy(update={"id": "B", "mandatory": True})
    result = run_scoring(make_dataset([make_person("PX", 100)], [first, second]))
    assert result.get_candidate("A").business_value_score == result.get_candidate("B").business_value_score


def test_commercial_expected_margin_and_full_hours_are_reused() -> None:
    work = make_work_item("WX", 10, wtype="sales_opportunity").model_copy(
        update={"strategic_value": 3}
    )
    dataset = make_dataset([make_person("PX", 500)], [work]).model_copy(
        update={"commercial_options": [commercial_option()]}
    )
    candidate = run_scoring(dataset).get_candidate("WX-A")
    economic = candidate.get_component(ComponentName.ECONOMIC_VALUE)
    efficiency = candidate.get_component(ComponentName.CAPACITY_EFFICIENCY)
    assert economic.raw_value == 300  # Phase 2C: (1000-400)*0.5
    assert efficiency.raw_value == pytest.approx(300 / 110)
    assert efficiency.evidence["committed_hours"] == 110
    assert efficiency.evidence["hours_source"] == "phase_2c_total_committed_hours_if_won"
    assert efficiency.raw_value != pytest.approx(300 / 60)  # base + expected delivery


def test_follow_on_cash_strategic_and_urgency_components() -> None:
    work = make_work_item(
        "WX", 10, wtype="sales_opportunity", due_date=date(2026, 10, 10)
    ).model_copy(update={"strategic_value": 4, "late_penalty_jpy_per_day": 100})
    dataset = make_dataset([make_person("PX", 500)], [work]).model_copy(
        update={"commercial_options": [commercial_option(follow_on=1_000, payment_days=27)]}
    )
    candidate = run_scoring(dataset).get_candidate("WX-A")
    assert candidate.get_component(ComponentName.FOLLOW_ON_VALUE).raw_value == 500
    assert candidate.get_component(ComponentName.CASH_TIMING).normalized_value == pytest.approx(0.5)
    assert candidate.get_component(ComponentName.STRATEGIC_CUSTOMER).raw_value == 4
    urgency = candidate.get_component(ComponentName.URGENCY_COST_OF_DELAY)
    assert urgency.normalized_value == pytest.approx((1 - 5 / 27 + 1) / 2)


def test_quality_risk_is_explicit_and_configurable() -> None:
    trigger = make_work_item("PRE", 5)
    target = make_work_item("WX", 10).model_copy(update={"strategic_value": 3})
    effect = PortfolioEffect(
        id="E", trigger="PRE", targets=["WX"], effect={"type": "quality_prerequisite"}
    )
    dataset = make_dataset([make_person("PX", 100)], [trigger, target]).model_copy(
        update={"portfolio_effects": [effect]}
    )
    candidate = run_scoring(dataset).get_candidate("WX")
    risk = candidate.get_component(ComponentName.RISK_RESILIENCE)
    assert risk.applicable is True
    assert risk.normalized_value == 0.5
    assert any(w.code.value == "PORTFOLIO_RISK_PRESENT" for w in candidate.warnings)


def test_na_weights_renormalize_and_zero_is_distinct_from_na() -> None:
    candidate = run_scoring(simple_dataset(revenue=0, cost=0)).candidates[0]
    economic = candidate.get_component(ComponentName.ECONOMIC_VALUE)
    follow_on = candidate.get_component(ComponentName.FOLLOW_ON_VALUE)
    assert economic.applicable is True
    assert economic.raw_value == 0
    assert economic.normalized_value == 0
    assert follow_on.applicable is False
    assert follow_on.normalized_value is None
    assert sum(c.effective_weight for c in candidate.components) == pytest.approx(1.0)
    assert follow_on.effective_weight == 0


def test_ties_normalize_deterministically() -> None:
    a = make_work_item("A", 10).model_copy(update={"revenue_jpy": 1_000, "strategic_value": 3})
    b = a.model_copy(update={"id": "B"})
    result = run_scoring(make_dataset([make_person("PX", 100)], [a, b]))
    assert result.get_candidate("A").get_component("economic_value").normalized_value == result.get_candidate("B").get_component("economic_value").normalized_value


def test_reference_reuse_produces_same_scores() -> None:
    dataset = simple_dataset()
    first = run_scoring(dataset)
    second = run_scoring(dataset, reference=first.normalization_reference)
    assert first.candidates[0].business_value_score == second.candidates[0].business_value_score
    assert second.reference_usage.value == "REUSED"
    assert second.normalization_reference == first.normalization_reference


@pytest.fixture(scope="module")
def canonical_scoring():
    root = Path(__file__).resolve().parents[2]
    dataset = load_dataset(root / "data/candidate_dataset.json", root / "data/candidate_dataset.schema.json")
    return dataset, run_scoring(dataset)


def test_canonical_candidate_shape_and_no_synthetic_no_bid(canonical_scoring) -> None:
    _, result = canonical_scoring
    assert len(result.candidates) == 35
    assert sum(c.action_type == ActionType.SELECT_OPTION for c in result.candidates) == 18
    assert result.get_candidate("NO_BID") is None


def test_canonical_commercial_and_noncommercial_scoring(canonical_scoring) -> None:
    _, result = canonical_scoring
    assert result.get_candidate("W008-A").action_type == ActionType.SELECT_OPTION
    assert result.get_candidate("W001").action_type == ActionType.DO_WORK_ITEM
    assert result.get_candidate("W001").business_value_score is not None


def test_canonical_w007_b_locked_regardless_of_score(canonical_scoring) -> None:
    _, result = canonical_scoring
    candidate = result.get_candidate("W007-B")
    assert candidate.selection_status == SelectionStatus.LOCKED
    assert candidate.eligible_for_selection is False
    assert candidate.business_value_score is not None


def test_canonical_w006_blocked_and_w011_c_is_ordinary(canonical_scoring) -> None:
    _, result = canonical_scoring
    assert all(result.get_candidate(f"W006-{suffix}").selection_status == SelectionStatus.BLOCKED for suffix in "AB")
    assert result.get_candidate("W006-C").selection_status == SelectionStatus.INFEASIBLE
    w011c = result.get_candidate("W011-C")
    assert w011c.action_type == ActionType.SELECT_OPTION
    assert w011c.selection_status == SelectionStatus.ELIGIBLE


def test_scoring_api_all_single_and_404() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/scoring")
    assert response.status_code == 200
    assert len(response.json()["candidates"]) == 35
    assert client.get("/api/v1/scoring/W007-B").json()["selection_status"] == "LOCKED"
    assert client.get("/api/v1/scoring/UNKNOWN").status_code == 404
