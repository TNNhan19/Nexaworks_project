"""Tests for multiplicative compounding of multiple hours_reduction effects.

Covers:
- Two reductions on one target
- Order independence
- Idempotency
- Base hours preserved
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
    make_portfolio_effect,
    make_work_item,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_hours_effect(eid: str, trigger: str, targets: list[str], reduction: float):
    return make_portfolio_effect(
        eid, trigger=trigger, targets=targets,
        effect_dict={"type": "hours_reduction", "value": reduction},
    )


# ===========================================================================
# Test A — two reductions compounded correctly
# ===========================================================================

def test_two_reductions_compounded_multiplicatively(engine):
    """Two active hours_reduction effects on same target use MULTIPLICATIVE_COMPOUNDING.

    base = 100
    effect A: 20% reduction  → factor 0.80
    effect B: 25% reduction  → factor 0.75
    expected effective = 100 * 0.80 * 0.75 = 60.0
    """
    trig_a = make_work_item("TRIG_A", 20)
    trig_b = make_work_item("TRIG_B", 20)
    target = make_work_item("TGT", 100)

    effects = [
        make_hours_effect("EA", "TRIG_A", ["TGT"], 0.20),
        make_hours_effect("EB", "TRIG_B", ["TGT"], 0.25),
    ]
    dataset = make_dataset([trig_a, trig_b, target], effects)
    ctx = build_context(dataset, completed={"TRIG_A", "TRIG_B"})
    result = engine.evaluate(dataset, ctx)

    state = result.work_item_states["TGT"]
    assert state.base_required_hours == 100.0
    assert abs(state.effective_required_hours - 60.0) < 1e-9  # 100 * 0.80 * 0.75

    # Net reduction fraction = 1 - 0.80*0.75 = 1 - 0.60 = 0.40
    override = result.work_item_states["TGT"].portfolio_warnings
    # Check collision warning was emitted
    collision = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.HOURS_REDUCTION_COLLISION_COMPOUNDED
    ]
    assert len(collision) == 1
    detail = collision[0].details
    assert detail["target_work_item_id"] == "TGT"
    assert detail["base_required_hours"] == 100.0
    assert abs(detail["effective_required_hours"] - 60.0) < 1e-9
    assert abs(detail["net_reduction_fraction"] - 0.40) < 1e-9
    assert detail["combination_policy"] == "multiplicative_compounding"

    # Both contributing effects appear in evidence
    contrib_ids = {c["effect_id"] for c in detail["contributing_effects"]}
    assert contrib_ids == {"EA", "EB"}
    contrib_fractions = {c["reduction_fraction"] for c in detail["contributing_effects"]}
    assert 0.20 in contrib_fractions
    assert 0.25 in contrib_fractions


def test_two_reductions_one_trigger_not_satisfied(engine):
    """Only one trigger satisfied → single reduction applied, no compounding."""
    trig_a = make_work_item("TRIG_A", 20)
    trig_b = make_work_item("TRIG_B", 20)
    target = make_work_item("TGT", 100)

    effects = [
        make_hours_effect("EA", "TRIG_A", ["TGT"], 0.20),
        make_hours_effect("EB", "TRIG_B", ["TGT"], 0.25),
    ]
    dataset = make_dataset([trig_a, trig_b, target], effects)
    ctx = build_context(dataset, completed={"TRIG_A"})  # only A satisfied
    result = engine.evaluate(dataset, ctx)

    state = result.work_item_states["TGT"]
    assert abs(state.effective_required_hours - 80.0) < 1e-9  # 100 * 0.80 only

    # No collision warning — only one reduction was active
    collision = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.HOURS_REDUCTION_COLLISION_COMPOUNDED
    ]
    assert collision == []


# ===========================================================================
# Test B — order independence
# ===========================================================================

def test_two_reductions_order_independent(engine):
    """MULTIPLICATIVE_COMPOUNDING is commutative — effect A before B or B before A
    produces identical effective hours.

    100 * 0.80 * 0.75  ==  100 * 0.75 * 0.80  ==  60.0
    """
    trig_a = make_work_item("TRIG_A", 20)
    trig_b = make_work_item("TRIG_B", 20)
    target = make_work_item("TGT", 100)

    # Order 1: A then B
    effects_ab = [
        make_hours_effect("EA", "TRIG_A", ["TGT"], 0.20),
        make_hours_effect("EB", "TRIG_B", ["TGT"], 0.25),
    ]
    ds_ab = make_dataset([trig_a, trig_b, target], effects_ab)
    ctx = build_context(ds_ab, completed={"TRIG_A", "TRIG_B"})
    result_ab = engine.evaluate(ds_ab, ctx)

    # Order 2: B then A
    effects_ba = [
        make_hours_effect("EB", "TRIG_B", ["TGT"], 0.25),
        make_hours_effect("EA", "TRIG_A", ["TGT"], 0.20),
    ]
    ds_ba = make_dataset([trig_a, trig_b, target], effects_ba)
    result_ba = engine.evaluate(ds_ba, ctx)

    eff_ab = result_ab.work_item_states["TGT"].effective_required_hours
    eff_ba = result_ba.work_item_states["TGT"].effective_required_hours

    assert abs(eff_ab - 60.0) < 1e-9
    assert abs(eff_ba - 60.0) < 1e-9
    assert abs(eff_ab - eff_ba) < 1e-9  # identical regardless of declaration order


def test_three_reductions_order_independent(engine):
    """Three active reductions — same effective regardless of declaration order."""
    wis = [make_work_item(f"TRIG_{i}", 10) for i in range(3)]
    target = make_work_item("TGT", 200)

    # 200 * 0.80 * 0.70 * 0.90 = 200 * 0.504 = 100.8
    fracs = [0.20, 0.30, 0.10]
    effects_fwd = [
        make_hours_effect(f"E{i}", f"TRIG_{i}", ["TGT"], fracs[i])
        for i in range(3)
    ]
    effects_rev = [
        make_hours_effect(f"E{i}", f"TRIG_{i}", ["TGT"], fracs[i])
        for i in range(2, -1, -1)
    ]
    all_trigs = {f"TRIG_{i}" for i in range(3)}
    all_wis = wis + [target]

    ds_fwd = make_dataset(all_wis, effects_fwd)
    ds_rev = make_dataset(all_wis, effects_rev)
    ctx = build_context(ds_fwd, completed=all_trigs)

    r_fwd = engine.evaluate(ds_fwd, ctx)
    r_rev = engine.evaluate(ds_rev, ctx)

    expected = 200 * 0.80 * 0.70 * 0.90  # 100.8
    assert abs(r_fwd.work_item_states["TGT"].effective_required_hours - expected) < 1e-9
    assert abs(r_rev.work_item_states["TGT"].effective_required_hours - expected) < 1e-9


# ===========================================================================
# Test C — idempotency with multiple effects
# ===========================================================================

def test_compounding_is_idempotent(engine):
    """Running evaluate() twice on same context with two effects yields same result."""
    trig_a = make_work_item("TRIG_A", 20)
    trig_b = make_work_item("TRIG_B", 20)
    target = make_work_item("TGT", 100)
    effects = [
        make_hours_effect("EA", "TRIG_A", ["TGT"], 0.20),
        make_hours_effect("EB", "TRIG_B", ["TGT"], 0.25),
    ]
    dataset = make_dataset([trig_a, trig_b, target], effects)
    ctx = build_context(dataset, completed={"TRIG_A", "TRIG_B"})

    r1 = engine.evaluate(dataset, ctx)
    r2 = engine.evaluate(dataset, ctx)

    assert abs(r1.work_item_states["TGT"].effective_required_hours - 60.0) < 1e-9
    assert abs(r2.work_item_states["TGT"].effective_required_hours - 60.0) < 1e-9
    assert r1.work_item_states["TGT"].effective_required_hours == \
           r2.work_item_states["TGT"].effective_required_hours
    assert len(r1.warnings) == len(r2.warnings)
    assert len([w for w in r1.warnings
                if w.code == PortfolioEffectCode.HOURS_REDUCTION_COLLISION_COMPOUNDED]) == 1


# ===========================================================================
# Test D — base hours preserved
# ===========================================================================

def test_base_hours_preserved_after_compounding(engine):
    """base_required_hours must equal the canonical value regardless of compounding."""
    trig_a = make_work_item("TRIG_A", 20)
    trig_b = make_work_item("TRIG_B", 20)
    target = make_work_item("TGT", 100)
    effects = [
        make_hours_effect("EA", "TRIG_A", ["TGT"], 0.20),
        make_hours_effect("EB", "TRIG_B", ["TGT"], 0.25),
    ]
    dataset = make_dataset([trig_a, trig_b, target], effects)
    ctx = build_context(dataset, completed={"TRIG_A", "TRIG_B"})
    result = engine.evaluate(dataset, ctx)

    state = result.work_item_states["TGT"]
    assert state.base_required_hours == 100.0  # canonical, never changed
    assert abs(state.effective_required_hours - 60.0) < 1e-9  # compounded
    assert state.hours_override_applied is True

    # Canonical dataset not mutated
    canonical_target = next(w for w in dataset.work_items if w.id == "TGT")
    assert canonical_target.required_hours == 100.0  # unchanged


def test_base_hours_preserved_in_applied_reductions_evidence(engine):
    """Each applied_reduction record carries the per-effect fraction, not the compounded result."""
    trig_a = make_work_item("TRIG_A", 20)
    trig_b = make_work_item("TRIG_B", 20)
    target = make_work_item("TGT", 100)
    effects = [
        make_hours_effect("EA", "TRIG_A", ["TGT"], 0.20),
        make_hours_effect("EB", "TRIG_B", ["TGT"], 0.25),
    ]
    dataset = make_dataset([trig_a, trig_b, target], effects)
    ctx = build_context(dataset, completed={"TRIG_A", "TRIG_B"})
    result = engine.evaluate(dataset, ctx)

    collision = next(
        w for w in result.warnings
        if w.code == PortfolioEffectCode.HOURS_REDUCTION_COLLISION_COMPOUNDED
    )
    # Check each contributing effect's fraction is the declared fraction, not the net
    fractions = {c["reduction_fraction"] for c in collision.details["contributing_effects"]}
    assert 0.20 in fractions
    assert 0.25 in fractions
    # Net fraction is separate
    assert abs(collision.details["net_reduction_fraction"] - 0.40) < 1e-9


def test_single_reduction_no_collision_warning(engine):
    """When only one reduction targets a work item, no collision warning is emitted."""
    trig = make_work_item("TRIG", 20)
    target = make_work_item("TGT", 100)
    effects = [make_hours_effect("EA", "TRIG", ["TGT"], 0.25)]
    dataset = make_dataset([trig, target], effects)
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    collision = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.HOURS_REDUCTION_COLLISION_COMPOUNDED
    ]
    assert collision == []
    assert result.work_item_states["TGT"].effective_required_hours == 75.0


def test_assumption_registry_has_policy_field():
    """AssumptionRegistry exposes the hours_reduction_combination_policy field."""
    from app.decision_engine.assumptions import AssumptionRegistry
    reg = AssumptionRegistry()
    assert reg.hours_reduction_combination_policy == "multiplicative_compounding"
