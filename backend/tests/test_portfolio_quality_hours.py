"""Tests for quality_prerequisite, hours_reduction, and idempotency.

Covers spec tests 1–6 (quality + deterministic hours).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.decision_engine.feasibility import FeasibilityEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.portfolio.reason_codes import PortfolioEffectCode

from conftest_portfolio import (
    build_context,
    engine,
    make_dataset,
    make_portfolio_effect,
    make_work_item,
)


# ===========================================================================
# Tests 1 & 2 — quality_prerequisite
# ===========================================================================

def _quality_effect(trigger: str, targets: list[str]):
    return make_portfolio_effect(
        "EQP",
        trigger=trigger,
        targets=targets,
        effect_dict={"type": "quality_prerequisite"},
    )


def test_quality_prerequisite_inactive_emits_risk_warning(engine):
    """Test 1: trigger not completed → QUALITY_PREREQUISITE_RISK for each target."""
    trigger_w = make_work_item("TRIG", 20)
    target_w1 = make_work_item("TGT1", 50)
    target_w2 = make_work_item("TGT2", 60)
    dataset = make_dataset(
        [trigger_w, target_w1, target_w2],
        [_quality_effect("TRIG", ["TGT1", "TGT2"])],
    )
    ctx = build_context(dataset, completed=set())  # TRIG not completed
    result = engine.evaluate(dataset, ctx)

    risk_warnings = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_RISK
    ]
    assert len(risk_warnings) == 2  # one per target
    target_ids = {w.target_id for w in risk_warnings}
    assert target_ids == {"TGT1", "TGT2"}
    # Verify evidence structure
    for w in risk_warnings:
        assert w.details["trigger_completed"] is False
        assert w.details["risk"] == "ELEVATED"
        assert w.details["quantitative_impact_known"] is False


def test_quality_prerequisite_satisfied_emits_satisfied_not_risk(engine):
    """Test 2: trigger completed → QUALITY_PREREQUISITE_SATISFIED, no RISK warning."""
    trigger_w = make_work_item("TRIG", 20)
    target_w = make_work_item("TGT1", 50)
    dataset = make_dataset([trigger_w, target_w], [_quality_effect("TRIG", ["TGT1"])])
    ctx = build_context(dataset, completed={"TRIG"})  # completed
    result = engine.evaluate(dataset, ctx)

    risk_warnings = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_RISK
    ]
    assert risk_warnings == []

    satisfied = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_SATISFIED
    ]
    assert len(satisfied) == 1
    assert satisfied[0].details["trigger_completed"] is True
    assert satisfied[0].details["risk"] == "NORMAL"


def test_quality_prerequisite_does_not_create_hard_dependency(engine):
    """Test 3: quality_prerequisite must NOT create BLOCKED/INFEASIBLE via Feasibility.

    The canonical dataset has W005→{W001,W006,W007} as both E001 and direct deps.
    This test verifies that a quality_prerequisite effect alone (without a direct
    work_item.dependencies entry) does NOT cause the feasibility engine to BLOCK.
    """
    trigger_w = make_work_item("TRIG", 20)
    target_w = make_work_item("TGT", 50)  # NO dependencies field set
    dataset = make_dataset([trigger_w, target_w], [_quality_effect("TRIG", ["TGT"])])

    # Portfolio: TRIG not completed → risk warning
    ctx = build_context(dataset, completed=set())
    pe_result = engine.evaluate(dataset, ctx)
    risk_warnings = [w for w in pe_result.warnings if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_RISK]
    assert len(risk_warnings) == 1  # warning emitted

    # Feasibility: TGT has no work_item.dependencies → must NOT be BLOCKED
    fe = FeasibilityEngine()
    w_target = next(w for w in dataset.work_items if w.id == "TGT")
    feasibility_result = fe.check_work_item(w_target, dataset)
    from app.decision_engine.feasibility import FeasibilityStatus
    assert feasibility_result.status == FeasibilityStatus.FEASIBLE, (
        "quality_prerequisite alone must not cause BLOCKED status in Feasibility Engine"
    )
    assert feasibility_result.dependencies.satisfied is True


# ===========================================================================
# Tests 4 & 5 — hours_reduction (deterministic)
# ===========================================================================

def _hours_effect(trigger: str, targets: list[str], reduction: float = 0.25):
    return make_portfolio_effect(
        "EHR",
        trigger=trigger,
        targets=targets,
        effect_dict={"type": "hours_reduction", "value": reduction},
    )


def test_deterministic_hours_reduction_applied_correctly(engine):
    """Test 4: trigger satisfied → effective_hours = base * (1 - reduction)."""
    trigger_w = make_work_item("TRIG", 30)
    target_w = make_work_item("TGT", 100)
    dataset = make_dataset([trigger_w, target_w], [_hours_effect("TRIG", ["TGT"], 0.25)])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    state = result.work_item_states["TGT"]
    assert state.base_required_hours == 100.0
    assert state.effective_required_hours == 75.0
    assert state.hours_override_applied is True

    applied_warnings = [
        w for w in result.warnings if w.code == PortfolioEffectCode.HOURS_REDUCTION_APPLIED
    ]
    assert len(applied_warnings) == 1
    assert applied_warnings[0].details["reduction_fraction"] == 0.25
    assert applied_warnings[0].details["effective_required_hours"] == 75.0


def test_hours_reduction_not_applied_when_trigger_not_satisfied(engine):
    """Test 4b: trigger not satisfied → effective_hours equals base."""
    trigger_w = make_work_item("TRIG", 30)
    target_w = make_work_item("TGT", 100)
    dataset = make_dataset([trigger_w, target_w], [_hours_effect("TRIG", ["TGT"], 0.25)])
    ctx = build_context(dataset, completed=set())  # TRIG not done
    result = engine.evaluate(dataset, ctx)

    # effective hours should still show in state (populated from warnings) but not overridden
    # The work item appears in work_item_states because it's referenced in warnings
    not_applied = [
        w for w in result.warnings if w.code == PortfolioEffectCode.HOURS_REDUCTION_NOT_APPLIED
    ]
    assert len(not_applied) == 1
    assert not_applied[0].details["effective_required_hours"] == 100.0
    assert not_applied[0].details["trigger_satisfied"] is False
    # Confirm no override applied
    assert result.get_effective_hours("TGT", base_hours=100.0) == 100.0


def test_hours_reduction_calculated_from_base_not_from_previously_reduced_value(engine):
    """Test 5: hours_reduction always derives from canonical base.

    Two evaluations on the same context must NOT stack the reduction.
    75h → 75h (not 75 * 0.75 = 56.25h).
    """
    trigger_w = make_work_item("TRIG", 30)
    target_w = make_work_item("TGT", 100)
    dataset = make_dataset([trigger_w, target_w], [_hours_effect("TRIG", ["TGT"], 0.25)])
    ctx = build_context(dataset, completed={"TRIG"})

    result1 = engine.evaluate(dataset, ctx)
    result2 = engine.evaluate(dataset, ctx)

    assert result1.work_item_states["TGT"].effective_required_hours == 75.0
    assert result2.work_item_states["TGT"].effective_required_hours == 75.0


# ===========================================================================
# Test 6 — idempotency (full engine level)
# ===========================================================================

def test_repeated_evaluation_is_idempotent(engine):
    """Test 6: running the engine twice on the same context yields identical results."""
    trigger_w = make_work_item("TRIG", 20)
    target_w = make_work_item("TGT", 80)
    eff = make_portfolio_effect(
        "EHR", trigger="TRIG", targets=["TGT"],
        effect_dict={"type": "hours_reduction", "value": 0.20},
    )
    dataset = make_dataset([trigger_w, target_w], [eff])
    ctx = build_context(dataset, completed={"TRIG"})

    r1 = engine.evaluate(dataset, ctx)
    r2 = engine.evaluate(dataset, ctx)

    assert r1.work_item_states["TGT"].effective_required_hours == \
           r2.work_item_states["TGT"].effective_required_hours == 64.0
    assert len(r1.warnings) == len(r2.warnings)
    assert len(r1.effects) == len(r2.effects)


def test_idempotency_with_all_effect_types(engine):
    """Idempotency with multiple effects — run twice, assert identical results."""
    from app.domain.models import CommercialOption
    trigger_w = make_work_item("TRIG", 50)
    target_w = make_work_item("TGT", 100)
    option = CommercialOption(
        work_item_id="TGT", option_id="OPT-X",
        label="Option X", price_jpy=500_000,
        delivery_hours=50.0, estimated_win_probability=0.5,
    )
    effects = [
        make_portfolio_effect("E1", "TRIG", ["TGT"], {"type": "quality_prerequisite"}),
        make_portfolio_effect("E2", "TRIG", ["TGT"], {"type": "hours_reduction", "value": 0.1}),
        make_portfolio_effect("E3", "TRIG", ["OPT-X"], {"type": "commercial_option_unlock"}),
    ]
    dataset = make_dataset([trigger_w, target_w], effects, commercial_options=[option])
    ctx = build_context(dataset, completed={"TRIG"})

    r1 = engine.evaluate(dataset, ctx)
    r2 = engine.evaluate(dataset, ctx)

    # Effective hours identical
    assert r1.get_effective_hours("TGT", 100.0) == r2.get_effective_hours("TGT", 100.0)
    # Option state identical
    assert r1.is_option_available("OPT-X") == r2.is_option_available("OPT-X")
    # Warning count identical
    assert len(r1.warnings) == len(r2.warnings)
