"""Commercial, portfolio, scoring, and planner behavior with arbitrary IDs."""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.decision_engine.commercial import (
    CommercialEvaluationEngine,
    OptionAvailabilityStatus,
)
from app.decision_engine.planner import DecisionType, PlannerEngine
from app.decision_engine.portfolio import PortfolioEffectCode, PortfolioEffectsEngine
from app.decision_engine.scoring import ScoringEngine
from app.decision_engine.scoring.reason_codes import ReferenceUsage

from .factories import (
    PLAN_START,
    make_dataset,
    make_effect,
    make_option,
    make_person,
    make_work_item,
)


def _upstream(dataset, completed=frozenset()):
    portfolio_engine = PortfolioEffectsEngine()
    portfolio = portfolio_engine.evaluate(
        dataset,
        portfolio_engine.build_context_from_dataset(
            dataset,
            completed_work_item_ids=completed,
        ),
    )
    commercial = CommercialEvaluationEngine().evaluate(
        dataset,
        portfolio,
        completed_ids=completed,
    )
    return portfolio, commercial


def test_five_arbitrary_option_ids_are_mutually_exclusive_without_suffix_rules():
    opportunity = make_work_item("MARKET_ENTRY", hours=0, work_type="sales_opportunity")
    ids = ["BRONZE", "SILVER_PLUS", "GOLD-PACKAGE", "ENTERPRISE_2027", "CUSTOM"]
    options = [
        make_option("MARKET_ENTRY", option_id, price=index * 100, delivery_hours=0)
        for index, option_id in enumerate(ids)
    ]
    dataset = make_dataset(work_items=[opportunity], options=options)
    portfolio, commercial = _upstream(dataset)
    plan = PlannerEngine().plan(dataset)
    assert [option.option_id for option in commercial.opportunities[0].options] == ids
    assert len(set(plan.selected_actions) & set(ids)) == 1
    assert sum(d.decision == DecisionType.SELECT_OPTION for d in plan.decisions) == 1


def test_canonical_looking_zero_value_option_is_not_inferred_as_no_bid():
    opportunity = make_work_item("SALES_CASE", hours=0, work_type="sales_opportunity")
    zero = make_option("SALES_CASE", "W999-C", price=0, cost=0, delivery_hours=0, probability=0)
    plan = PlannerEngine().plan(make_dataset(work_items=[opportunity], options=[zero]))
    assert "W999-C" in plan.selected_actions
    assert plan.get_decision("W999-C").decision == DecisionType.SELECT_OPTION
    assert "SALES_CASE" not in plan.no_bid_opportunities


def test_locked_arbitrary_option_unlocks_only_when_declared_trigger_is_completed():
    trigger = make_work_item("SECURITY_REVIEW")
    opportunity = make_work_item("NEW_REGION", hours=0, work_type="sales_opportunity")
    option = make_option("NEW_REGION", "REGION_LAUNCH", delivery_hours=0)
    unlock = make_effect(
        "DECLARED_UNLOCK",
        trigger="SECURITY_REVIEW",
        targets=["REGION_LAUNCH"],
        effect_type="commercial_option_unlock",
    )
    dataset = make_dataset(work_items=[trigger, opportunity], options=[option], effects=[unlock])
    _, locked = _upstream(dataset)
    _, unlocked = _upstream(dataset, frozenset({"SECURITY_REVIEW"}))
    assert locked.get_option("REGION_LAUNCH").availability == OptionAvailabilityStatus.LOCKED
    assert unlocked.get_option("REGION_LAUNCH").availability == OptionAvailabilityStatus.AVAILABLE


def test_arbitrary_option_expiry_uses_dates_not_identifier():
    expired = make_work_item(
        "PAST_OPPORTUNITY",
        hours=0,
        work_type="sales_opportunity",
        earliest=PLAN_START - timedelta(days=10),
        due=PLAN_START - timedelta(days=1),
    )
    dataset = make_dataset(
        work_items=[expired],
        options=[make_option("PAST_OPPORTUNITY", "TIME_LIMITED_DEAL")],
    )
    _, commercial = _upstream(dataset)
    assert commercial.get_option("TIME_LIMITED_DEAL").availability == OptionAvailabilityStatus.EXPIRED
    assert "PAST_OPPORTUNITY" in PlannerEngine().plan(dataset).no_bid_opportunities


def test_multiple_hours_reductions_compound_multiplicatively_and_order_independently():
    trigger_a = make_work_item("AUTOMATION_A")
    trigger_b = make_work_item("AUTOMATION_B")
    target = make_work_item("MANUAL_PROCESS", hours=100)
    effects = [
        make_effect("CUT_TWENTY", trigger="AUTOMATION_A", targets=["MANUAL_PROCESS"], effect_type="hours_reduction", value=0.2),
        make_effect("CUT_TEN", trigger="AUTOMATION_B", targets=["MANUAL_PROCESS"], effect_type="hours_reduction", value=0.1),
    ]
    completed = frozenset({"AUTOMATION_A", "AUTOMATION_B"})
    first_dataset = make_dataset(work_items=[trigger_a, trigger_b, target], effects=effects)
    second_dataset = first_dataset.model_copy(update={"portfolio_effects": list(reversed(effects))})
    first, _ = _upstream(first_dataset, completed)
    second, _ = _upstream(second_dataset, completed)
    assert first.get_effective_hours("MANUAL_PROCESS", 100) == pytest.approx(72)
    assert second.get_effective_hours("MANUAL_PROCESS", 100) == pytest.approx(72)


def test_all_declared_effect_categories_accept_noncanonical_ids():
    trigger = make_work_item("DISCOVERY_COMPLETE")
    target = make_work_item("FOLLOWUP_WORK", hours=10)
    opportunity = make_work_item("FOLLOWUP_SALE", hours=0, work_type="sales_opportunity")
    option = make_option("FOLLOWUP_SALE", "FOLLOWUP_PREMIUM", delivery_hours=0)
    effects = [
        make_effect("QUALITY_GATE", trigger="DISCOVERY_COMPLETE", targets=["FOLLOWUP_WORK"], effect_type="quality_prerequisite"),
        make_effect("FUTURE_SPEED", trigger="DISCOVERY_COMPLETE", targets=["FOLLOWUP_WORK"], effect_type="future_hours_reduction", value=0.4, probability=0.5),
        make_effect("SALE_UNLOCK", trigger="DISCOVERY_COMPLETE", targets=["FOLLOWUP_PREMIUM"], effect_type="commercial_option_unlock"),
        make_effect("COLLECTION_BONUS", trigger="DISCOVERY_COMPLETE", targets=["company_cash"], effect_type="cash_inflow", value_jpy=321, probability=0.25),
    ]
    dataset = make_dataset(work_items=[trigger, target, opportunity], options=[option], effects=effects)
    portfolio, _ = _upstream(dataset, frozenset({"DISCOVERY_COMPLETE"}))
    assert len(portfolio.effects) == 4
    assert portfolio.work_item_states["FOLLOWUP_WORK"].probabilistic_hours.success_case_hours == 6
    assert portfolio.is_option_available("FOLLOWUP_PREMIUM")
    assert portfolio.cash_effects[0].expected_cash_inflow_jpy == pytest.approx(80.25)


def test_unknown_effect_type_is_structured_not_crash():
    trigger = make_work_item("KNOWN_TRIGGER")
    target = make_work_item("KNOWN_TARGET")
    effect = make_effect(
        "UNKNOWN_EFFECT_ID",
        trigger="KNOWN_TRIGGER",
        targets=["KNOWN_TARGET"],
        effect_type="quantum_teleport",
    )
    portfolio, _ = _upstream(make_dataset(work_items=[trigger, target], effects=[effect]))
    assert portfolio.effects[0].applied is False
    assert any(w.code == PortfolioEffectCode.UNSUPPORTED_PORTFOLIO_EFFECT_TYPE for w in portfolio.warnings)


def test_scoring_one_candidate_zero_economics_and_no_positive_reference_values():
    dataset = make_dataset(work_items=[make_work_item(
        "ONLY_CANDIDATE",
        revenue=0,
        direct_cost=0,
        strategic_value=0,
    )])
    portfolio, commercial = _upstream(dataset)
    result = ScoringEngine().evaluate(dataset, portfolio, commercial)
    candidate = result.get_candidate("ONLY_CANDIDATE")
    assert candidate is not None
    assert candidate.business_value_score >= 0
    assert result.normalization_reference is not None


def test_scoring_reference_reuse_stabilizes_cross_scenario_scores():
    dataset = make_dataset(work_items=[
        make_work_item("TIED_BETA", revenue=100),
        make_work_item("TIED_ALPHA", revenue=100),
    ])
    portfolio, commercial = _upstream(dataset)
    built = ScoringEngine().evaluate(dataset, portfolio, commercial)
    reused = ScoringEngine().evaluate(
        dataset,
        portfolio,
        commercial,
        scoring_reference=built.normalization_reference,
    )
    assert reused.reference_usage == ReferenceUsage.REUSED
    assert [c.business_value_score for c in built.candidates] == [c.business_value_score for c in reused.candidates]
    plan = PlannerEngine().plan(
        make_dataset(
            people=[make_person("ONE_SLOT", capacity=1)],
            work_items=dataset.work_items,
            start=PLAN_START,
            end=PLAN_START,
        ),
        scoring_reference=built.normalization_reference,
    )
    assert plan.selected_actions == ["TIED_ALPHA"]


def test_mandatory_receives_no_hidden_scoring_bonus_with_arbitrary_ids():
    dataset = make_dataset(work_items=[
        make_work_item("REQUIRED_LOW_VALUE", mandatory=True, revenue=0),
        make_work_item("OPTIONAL_HIGH_VALUE", revenue=10_000),
    ])
    portfolio, commercial = _upstream(dataset)
    scores = ScoringEngine().evaluate(dataset, portfolio, commercial)
    assert scores.get_candidate("REQUIRED_LOW_VALUE").business_value_score < scores.get_candidate("OPTIONAL_HIGH_VALUE").business_value_score


def test_planner_no_bid_is_emitted_only_when_no_option_fits():
    opportunity = make_work_item("TOO_LARGE_SALE", hours=5, work_type="sales_opportunity")
    options = [make_option("TOO_LARGE_SALE", f"OFFER_{index}", delivery_hours=5) for index in range(4)]
    dataset = make_dataset(
        people=[make_person("TINY_TEAM", capacity=1)],
        work_items=[opportunity],
        options=options,
    )
    plan = PlannerEngine().plan(dataset)
    assert plan.no_bid_opportunities == ["TOO_LARGE_SALE"]
    assert plan.get_decision("TOO_LARGE_SALE").decision == DecisionType.NO_BID
