"""Tests 18–21: validation, canonical dataset regression, and Phase 2A regression.

Covers:
    18. Invalid effect target handled cleanly.
    19. Unsupported effect type handled cleanly.
    20. Canonical dataset regression (all five effects E001–E005).
    21. All Phase 2A tests remain green (indirect — just verify no import errors).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.portfolio import PortfolioEffectsEngine, PortfolioEvaluationContext
from app.decision_engine.portfolio.reason_codes import PortfolioEffectCode
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "candidate_dataset.json"
SCHEMA = ROOT / "data" / "candidate_dataset.schema.json"

from conftest_portfolio import (
    build_context,
    engine,
    make_dataset,
    make_option,
    make_portfolio_effect,
    make_work_item,
)


# ===========================================================================
# Test 18 — invalid effect target
# ===========================================================================

def test_invalid_work_item_target_handled_cleanly(engine):
    """Test 18a: target work item ID not in dataset → INVALID_PORTFOLIO_EFFECT_TARGET."""
    trig = make_work_item("TRIG", 20)
    # "GHOST" does not exist in the dataset
    eff = make_portfolio_effect(
        "E-BAD", trigger="TRIG", targets=["GHOST"],
        effect_dict={"type": "quality_prerequisite"},
    )
    dataset = make_dataset([trig], [eff])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    bad_codes = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TARGET
    ]
    assert len(bad_codes) == 1
    assert bad_codes[0].details.get("target_id") == "GHOST"
    # No unhandled exception
    assert len(result.effects) == 1


def test_invalid_commercial_option_target_handled_cleanly(engine):
    """Test 18b: target commercial option not in dataset → INVALID_PORTFOLIO_EFFECT_TARGET."""
    trig = make_work_item("TRIG", 20)
    eff = make_portfolio_effect(
        "E-BAD", trigger="TRIG", targets=["NONEXISTENT-OPT"],
        effect_dict={"type": "commercial_option_unlock"},
    )
    dataset = make_dataset([trig], [eff], commercial_options=[])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    bad_codes = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TARGET
    ]
    assert len(bad_codes) == 1


def test_invalid_trigger_handled_cleanly(engine):
    """Test 18c: trigger work item not in dataset → INVALID_PORTFOLIO_EFFECT_TRIGGER."""
    target_w = make_work_item("TGT", 50)
    eff = make_portfolio_effect(
        "E-BAD", trigger="GHOST_TRIG", targets=["TGT"],
        effect_dict={"type": "quality_prerequisite"},
    )
    dataset = make_dataset([target_w], [eff])
    ctx = build_context(dataset)
    result = engine.evaluate(dataset, ctx)

    bad_triggers = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TRIGGER
    ]
    assert len(bad_triggers) == 1
    assert bad_triggers[0].details.get("trigger_id") == "GHOST_TRIG"


# ===========================================================================
# Test 19 — unsupported effect type
# ===========================================================================

def test_unsupported_effect_type_handled_cleanly(engine):
    """Test 19: unknown effect.type → UNSUPPORTED_PORTFOLIO_EFFECT_TYPE, no exception."""
    trig = make_work_item("TRIG", 20)
    tgt = make_work_item("TGT", 50)
    eff = make_portfolio_effect(
        "E-UNK", trigger="TRIG", targets=["TGT"],
        effect_dict={"type": "teleportation_beam"},  # invented type
    )
    dataset = make_dataset([trig, tgt], [eff])
    ctx = build_context(dataset, completed={"TRIG"})
    result = engine.evaluate(dataset, ctx)

    unsupported = [
        w for w in result.warnings
        if w.code == PortfolioEffectCode.UNSUPPORTED_PORTFOLIO_EFFECT_TYPE
    ]
    assert len(unsupported) == 1
    assert unsupported[0].details["effect_type"] == "teleportation_beam"
    # Engine still returns a result with one evaluated effect
    assert len(result.effects) == 1
    assert result.effects[0].applied is False


# ===========================================================================
# Test 20 — canonical dataset regression
# ===========================================================================

@pytest.fixture(scope="module")
def canonical_dataset():
    return load_dataset(DATASET, SCHEMA)


@pytest.fixture(scope="module")
def canonical_result_base(canonical_dataset):
    """Base scenario: no work items completed."""
    eng = PortfolioEffectsEngine()
    ctx = PortfolioEffectsEngine.build_context_from_dataset(canonical_dataset)
    return eng.evaluate(canonical_dataset, ctx)


@pytest.fixture(scope="module")
def canonical_result_all_triggers(canonical_dataset):
    """All trigger work items completed."""
    eng = PortfolioEffectsEngine()
    # E001 trigger=W005, E002 trigger=W013, E003 trigger=W017,
    # E004 trigger=W022, E005 trigger=W021
    triggers = frozenset({"W005", "W013", "W017", "W022", "W021"})
    ctx = PortfolioEffectsEngine.build_context_from_dataset(
        canonical_dataset, completed_work_item_ids=triggers
    )
    return eng.evaluate(canonical_dataset, ctx)


def test_canonical_all_five_effects_evaluated(canonical_result_base):
    """All five declared effects are evaluated."""
    assert len(canonical_result_base.effects) == 5


def test_canonical_e001_trigger_not_satisfied_base(canonical_result_base, canonical_dataset):
    """E001 base: W005 not completed → QUALITY_PREREQUISITE_RISK for W001, W006, W007."""
    e001 = next(e for e in canonical_result_base.effects if e.effect_id == "E001")
    assert e001.trigger_satisfied is False
    risk_codes = [
        w for w in e001.warnings
        if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_RISK
    ]
    assert len(risk_codes) == 3
    target_ids = {w.target_id for w in risk_codes}
    assert target_ids == {"W001", "W006", "W007"}


def test_canonical_e001_trigger_satisfied(canonical_result_all_triggers):
    """E001 with W005 completed → QUALITY_PREREQUISITE_SATISFIED, no RISK warnings."""
    e001 = next(e for e in canonical_result_all_triggers.effects if e.effect_id == "E001")
    assert e001.trigger_satisfied is True
    risk = [w for w in e001.warnings if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_RISK]
    assert risk == []
    satisfied = [w for w in e001.warnings if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_SATISFIED]
    assert len(satisfied) == 3


def test_canonical_e002_base_hours_and_effective_hours(canonical_dataset, canonical_result_all_triggers):
    """E002: W013 trigger satisfied → W015 effective hours = base * 0.75."""
    w015 = next(w for w in canonical_dataset.work_items if w.id == "W015")
    base_hours = w015.required_hours  # 68h per dataset
    state = canonical_result_all_triggers.work_item_states.get("W015")
    assert state is not None
    assert state.base_required_hours == base_hours
    assert state.hours_override_applied is True
    assert abs(state.effective_required_hours - base_hours * 0.75) < 0.001


def test_canonical_e002_not_applied_base(canonical_result_base):
    """E002 base: W013 not completed → W015 effective hours unchanged."""
    effective = canonical_result_base.get_effective_hours(
        "W015",
        base_hours=next(
            e for e in canonical_result_base.effects if e.effect_id == "E002"
        ).warnings[0].details.get("base_required_hours", 68.0)
    )
    # Since trigger not satisfied, get_effective_hours returns base_hours
    assert effective == 68.0


def test_canonical_e003_probabilistic_impacts(canonical_result_all_triggers, canonical_dataset):
    """E003: W017 trigger satisfied → W010 and W019 get probabilistic scenarios."""
    for wid in ["W010", "W019"]:
        w = next(wi for wi in canonical_dataset.work_items if wi.id == wid)
        state = canonical_result_all_triggers.work_item_states.get(wid)
        assert state is not None
        ph = state.probabilistic_hours
        assert ph is not None
        assert ph.probability == 0.75
        assert ph.impact_fraction == 0.20
        assert abs(ph.expected_impact_fraction - 0.15) < 1e-9
        assert ph.success_case_hours == w.required_hours * 0.80
        assert ph.downside_case_hours == w.required_hours
        # Committed hours NOT overwritten
        assert state.hours_override_applied is False
        assert state.effective_required_hours == w.required_hours


def test_canonical_e004_option_locked_base(canonical_result_base):
    """E004 base: W022 not completed → W007-B is LOCKED."""
    assert canonical_result_base.is_option_available("W007-B") is False
    state = canonical_result_base.commercial_option_states["W007-B"]
    assert state.available is False
    assert PortfolioEffectCode.COMMERCIAL_OPTION_LOCKED in state.reason_codes


def test_canonical_e004_option_available_when_triggered(canonical_result_all_triggers):
    """E004 with W022 completed → W007-B is AVAILABLE."""
    assert canonical_result_all_triggers.is_option_available("W007-B") is True
    state = canonical_result_all_triggers.commercial_option_states["W007-B"]
    assert state.available is True
    assert PortfolioEffectCode.COMMERCIAL_OPTION_UNLOCKED in state.reason_codes


def test_canonical_e005_cash_inflow_structured_values(canonical_result_all_triggers):
    """E005 with W021 completed → cash effect with correct probability/values."""
    assert len(canonical_result_all_triggers.cash_effects) == 1
    ce = canonical_result_all_triggers.cash_effects[0]
    assert ce.trigger_satisfied is True
    assert ce.probability == 0.85
    assert ce.cash_inflow_jpy == 3_800_000
    assert abs(ce.expected_cash_inflow_jpy - 3_230_000) < 1  # 3.8M * 0.85
    assert ce.success_case_cash_inflow_jpy == 3_800_000
    assert ce.downside_case_cash_inflow_jpy == 0.0


def test_canonical_e005_cash_zero_base(canonical_result_base):
    """E005 base: W021 not completed → all cash values are 0."""
    assert len(canonical_result_base.cash_effects) == 1
    ce = canonical_result_base.cash_effects[0]
    assert ce.trigger_satisfied is False
    assert ce.expected_cash_inflow_jpy == 0.0
    assert ce.success_case_cash_inflow_jpy == 0.0
    assert ce.downside_case_cash_inflow_jpy == 0.0


def test_canonical_result_deterministic(canonical_dataset):
    """Running engine twice on same context → identical results."""
    eng = PortfolioEffectsEngine()
    ctx = PortfolioEffectsEngine.build_context_from_dataset(canonical_dataset)
    r1 = eng.evaluate(canonical_dataset, ctx)
    r2 = eng.evaluate(canonical_dataset, ctx)
    assert len(r1.effects) == len(r2.effects)
    assert len(r1.warnings) == len(r2.warnings)
    assert r1.is_option_available("W007-B") == r2.is_option_available("W007-B")


# ===========================================================================
# Test 21 — Phase 2A tests regression (verify feasibility engine unaffected)
# ===========================================================================

def test_phase_2a_feasibility_engine_still_works_without_override(canonical_dataset):
    """Test 21: FeasibilityEngine with no effective_hours_override behaves identically.

    This verifies backward compatibility: adding the optional parameter
    does not break the existing 45 Phase 2A tests.
    """
    fe = FeasibilityEngine()
    results = fe.check_all(canonical_dataset)
    assert len(results) == 24

    # W001 must still be BLOCKED (Phase 2A regression)
    w001 = next(r for r in results if r.work_item_id == "W001")
    assert w001.status == FeasibilityStatus.BLOCKED

    # No item should be INFEASIBLE (as verified in Phase 2A)
    infeasible = [r for r in results if r.status == FeasibilityStatus.INFEASIBLE]
    assert infeasible == []


def test_phase_2a_feasibility_with_portfolio_hours_override(canonical_dataset):
    """Phase 2A feasibility correctly uses effective hours when override is provided.

    This tests the integration path: Portfolio Effects → Feasibility Engine.
    """
    # E002: W013 trigger completed → W015 gets 25% reduction
    pe_engine = PortfolioEffectsEngine()
    ctx = PortfolioEffectsEngine.build_context_from_dataset(
        canonical_dataset, completed_work_item_ids=frozenset({"W013"})
    )
    pe_result = pe_engine.evaluate(canonical_dataset, ctx)

    # Build the effective_hours_override map from portfolio result
    override_map = {
        wid: state.effective_required_hours
        for wid, state in pe_result.work_item_states.items()
        if state.hours_override_applied
    }

    # W015 should have an effective hours override
    assert "W015" in override_map

    # Run feasibility with the override
    fe = FeasibilityEngine()
    w015 = next(w for w in canonical_dataset.work_items if w.id == "W015")
    result_with_override = fe.check_work_item(
        w015, canonical_dataset, effective_hours_override=override_map
    )
    result_without_override = fe.check_work_item(
        w015, canonical_dataset
    )

    # Hours overrides do not change the skill-eligible capacity pool.
    eligible_capacity = sum(
        person.capacity_hours
        for person in canonical_dataset.people
        if any(
            person.skills.get(requirement.skill, 0) >= requirement.min_level
            for requirement in w015.required_skills
        )
    )
    assert result_with_override.capacity.total_team_capacity_hours == \
           result_without_override.capacity.total_team_capacity_hours == eligible_capacity

    # The override changes the required_hours in the capacity check
    assert result_with_override.capacity.required_hours < \
           result_without_override.capacity.required_hours
