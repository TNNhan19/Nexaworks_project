"""Tests for future_hours_reduction, commercial_option_unlock, and cash_inflow.

Covers spec tests 7–17.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.portfolio.reason_codes import PortfolioEffectCode

from conftest_portfolio import (
    build_context,
    engine,
    make_dataset,
    make_option,
    make_portfolio_effect,
    make_work_item,
)


# ===========================================================================
# Tests 7–10 — future_hours_reduction (probabilistic)
# ===========================================================================

def _future_hours_effect(trigger, targets, impact=0.20, prob=0.75):
    return make_portfolio_effect(
        "EFHR", trigger=trigger, targets=targets,
        effect_dict={"type": "future_hours_reduction", "value": impact, "probability": prob},
    )


def test_future_hours_reduction_expected_fraction_correct(engine):
    """Test 7: expected_impact_fraction = probability * impact_fraction."""
    trig = make_work_item("TRIG", 30)
    tgt = make_work_item("TGT", 100)
    dataset = make_dataset([trig, tgt], [_future_hours_effect("TRIG", ["TGT"], 0.20, 0.75)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    state = result.work_item_states["TGT"]
    assert state.probabilistic_hours is not None
    ph = state.probabilistic_hours
    assert ph.probability == 0.75
    assert ph.impact_fraction == 0.20
    assert abs(ph.expected_impact_fraction - 0.15) < 1e-9  # 0.75 * 0.20


def test_future_hours_reduction_success_case(engine):
    """Test 8: success case hours = base * (1 - impact_fraction)."""
    trig = make_work_item("TRIG", 30)
    tgt = make_work_item("TGT", 100)
    dataset = make_dataset([trig, tgt], [_future_hours_effect("TRIG", ["TGT"], 0.20, 0.75)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    ph = result.work_item_states["TGT"].probabilistic_hours
    assert ph.success_case_hours == 80.0  # 100 * (1 - 0.20)


def test_future_hours_reduction_downside_case(engine):
    """Test 9: downside case hours = base hours (unchanged)."""
    trig = make_work_item("TRIG", 30)
    tgt = make_work_item("TGT", 100)
    dataset = make_dataset([trig, tgt], [_future_hours_effect("TRIG", ["TGT"], 0.20, 0.75)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    ph = result.work_item_states["TGT"].probabilistic_hours
    assert ph.downside_case_hours == 100.0  # unchanged


def test_probabilistic_effect_does_not_overwrite_committed_base_hours(engine):
    """Test 10: future_hours_reduction does NOT change effective_required_hours.

    The committed operational plan (effective_required_hours) must stay at base.
    Only the probabilistic scenarios change.
    """
    trig = make_work_item("TRIG", 30)
    tgt = make_work_item("TGT", 100)
    dataset = make_dataset([trig, tgt], [_future_hours_effect("TRIG", ["TGT"], 0.20, 0.75)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    state = result.work_item_states["TGT"]
    # hours_override_applied must be False — probabilistic effects never override committed hours
    assert state.hours_override_applied is False
    # effective_required_hours equals base (NOT 80h, NOT 85h expected)
    assert state.effective_required_hours == 100.0
    # The base-derived accessor also returns base
    assert result.get_effective_hours("TGT", base_hours=100.0) == 100.0


def test_future_hours_trigger_not_satisfied_both_scenarios_equal_base(engine):
    """When trigger not satisfied, success and downside both equal base hours."""
    trig = make_work_item("TRIG", 30)
    tgt = make_work_item("TGT", 100)
    dataset = make_dataset([trig, tgt], [_future_hours_effect("TRIG", ["TGT"], 0.20, 0.75)])
    ctx = build_context(dataset, completed=set())  # TRIG not done
    result = engine.evaluate(dataset, ctx)

    ph = result.work_item_states["TGT"].probabilistic_hours
    assert ph.success_case_hours == 100.0
    assert ph.downside_case_hours == 100.0


# ===========================================================================
# Tests 11–13 — commercial_option_unlock
# ===========================================================================

def _unlock_effect(trigger, targets):
    return make_portfolio_effect(
        "ECOU", trigger=trigger, targets=targets,
        effect_dict={"type": "commercial_option_unlock"},
    )


def test_commercial_option_locked_when_trigger_not_satisfied(engine):
    """Test 11: trigger not satisfied → option LOCKED, COMMERCIAL_OPTION_LOCKED code."""
    trig = make_work_item("TRIG", 20)
    witem = make_work_item("WX", 50)
    option = make_option("OPT-LOCKED", "WX")
    dataset = make_dataset([trig, witem], [_unlock_effect("TRIG", ["OPT-LOCKED"])], [option])
    ctx = build_context(dataset, completed=set())
    result = engine.evaluate(dataset, ctx)

    assert result.is_option_available("OPT-LOCKED") is False
    state = result.commercial_option_states["OPT-LOCKED"]
    assert state.available is False
    assert PortfolioEffectCode.COMMERCIAL_OPTION_LOCKED in state.reason_codes


def test_commercial_option_available_when_trigger_satisfied(engine):
    """Test 12: trigger satisfied → option AVAILABLE, COMMERCIAL_OPTION_UNLOCKED code."""
    trig = make_work_item("TRIG", 20)
    witem = make_work_item("WX", 50)
    option = make_option("OPT-UNLOCKED", "WX")
    dataset = make_dataset([trig, witem], [_unlock_effect("TRIG", ["OPT-UNLOCKED"])], [option])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    assert result.is_option_available("OPT-UNLOCKED") is True
    state = result.commercial_option_states["OPT-UNLOCKED"]
    assert state.available is True
    assert PortfolioEffectCode.COMMERCIAL_OPTION_UNLOCKED in state.reason_codes


def test_commercial_unlock_does_not_rank_or_select_option(engine):
    """Test 13: unlock only sets availability — no score, rank, or selection produced."""
    trig = make_work_item("TRIG", 20)
    witem = make_work_item("WX", 50)
    option = make_option("OPT-A", "WX")
    dataset = make_dataset([trig, witem], [_unlock_effect("TRIG", ["OPT-A"])], [option])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    state = result.commercial_option_states["OPT-A"]
    # Available — but no ranking, scoring, or selection fields present
    assert state.available is True
    # State has no 'score', 'rank', or 'selected' attribute
    assert not hasattr(state, "score")
    assert not hasattr(state, "rank")
    assert not hasattr(state, "selected")


def test_option_not_subject_to_unlock_is_available_by_default(engine):
    """Options with no unlock effect are available by default."""
    witem = make_work_item("WX", 50)
    option = make_option("OPT-FREE", "WX")
    dataset = make_dataset([witem], [], [option])
    ctx = build_context(dataset)
    result = engine.evaluate(dataset, ctx)

    # Not referenced by any effect — available by default
    assert result.is_option_available("OPT-FREE") is True
    assert "OPT-FREE" not in result.commercial_option_states


# ===========================================================================
# Tests 14–17 — cash_inflow (probabilistic)
# ===========================================================================

def _cash_effect(trigger, targets, jpy=3_800_000, prob=0.85):
    return make_portfolio_effect(
        "ECI", trigger=trigger, targets=targets,
        effect_dict={"type": "cash_inflow", "value_jpy": jpy, "probability": prob},
    )


def test_cash_inflow_expected_value_correct(engine):
    """Test 14: expected = probability * value_jpy."""
    trig = make_work_item("TRIG", 20)
    dataset = make_dataset([trig], [_cash_effect("TRIG", ["company_cash"], 3_800_000, 0.85)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    assert len(result.cash_effects) == 1
    ce = result.cash_effects[0]
    assert abs(ce.expected_cash_inflow_jpy - 3_230_000) < 1  # 3.8M * 0.85


def test_cash_inflow_success_case_correct(engine):
    """Test 15: success case = full declared value."""
    trig = make_work_item("TRIG", 20)
    dataset = make_dataset([trig], [_cash_effect("TRIG", ["company_cash"], 3_800_000, 0.85)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    ce = result.cash_effects[0]
    assert ce.success_case_cash_inflow_jpy == 3_800_000


def test_cash_inflow_downside_is_zero(engine):
    """Test 16: downside case = 0 (collection fails)."""
    trig = make_work_item("TRIG", 20)
    dataset = make_dataset([trig], [_cash_effect("TRIG", ["company_cash"], 3_800_000, 0.85)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    ce = result.cash_effects[0]
    assert ce.downside_case_cash_inflow_jpy == 0.0


def test_cash_inflow_trigger_not_satisfied_all_values_zero(engine):
    """When trigger not satisfied, all cash values are zero."""
    trig = make_work_item("TRIG", 20)
    dataset = make_dataset([trig], [_cash_effect("TRIG", ["company_cash"], 3_800_000, 0.85)])
    ctx = build_context(dataset, completed=set())  # TRIG not done
    result = engine.evaluate(dataset, ctx)

    assert len(result.cash_effects) == 1
    ce = result.cash_effects[0]
    assert ce.trigger_satisfied is False
    assert ce.expected_cash_inflow_jpy == 0.0
    assert ce.success_case_cash_inflow_jpy == 0.0
    assert ce.downside_case_cash_inflow_jpy == 0.0


def test_probabilistic_cash_does_not_make_cash_automatically_feasible(engine):
    """Test 17: the engine provides analysis values — it does NOT commit cash.

    Downstream modules (Phase 2F) determine buffer sufficiency.
    The PortfolioEffectsResult has no 'cash_feasible' or 'cash_sufficient' flag.
    """
    trig = make_work_item("TRIG", 20)
    dataset = make_dataset([trig], [_cash_effect("TRIG", ["company_cash"], 50_000_000, 0.99)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    # No cash-feasibility judgment in the result
    assert not hasattr(result, "cash_feasible")
    assert not hasattr(result, "cash_sufficient")
    # Cash effects are present as structured data only
    assert len(result.cash_effects) == 1
