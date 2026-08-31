#!/usr/bin/env python
"""Portfolio Effects Engine -- canonical dataset analysis (Phase 2B).

Run:
    cd backend
    python scripts/run_portfolio_analysis.py

Output is a structured development report.
NOT a final business recommendation.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.portfolio.reason_codes import PortfolioEffectCode
from app.services.dataset_loader import load_dataset

DATASET = ROOT / "data" / "candidate_dataset.json"
SCHEMA = ROOT / "data" / "candidate_dataset.schema.json"

SEP = "-" * 70


def fmt_jpy(v: float) -> str:
    return f"¥{v:,.0f}"


def main():
    ds = load_dataset(DATASET, SCHEMA)
    engine = PortfolioEffectsEngine()

    # ---- Base scenario (no triggers satisfied) ----------------------------
    ctx_base = PortfolioEffectsEngine.build_context_from_dataset(ds)
    result_base = engine.evaluate(ds, ctx_base)

    # ---- All-triggers scenario -------------------------------------------
    all_triggers = frozenset(e.trigger for e in ds.portfolio_effects)
    ctx_all = PortfolioEffectsEngine.build_context_from_dataset(
        ds, completed_work_item_ids=all_triggers
    )
    result_all = engine.evaluate(ds, ctx_all)

    # ---- Build base_hours lookup -----------------------------------------
    base_hours = {w.id: w.required_hours for w in ds.work_items}

    print()
    print("=" * 70)
    print("NEXAWORKS -- PHASE 2B PORTFOLIO EFFECTS ANALYSIS")
    print(f"Dataset: {ds.metadata.dataset_id}  |  Planning: "
          f"{ds.metadata.planning_start} -> {ds.metadata.planning_end}")
    print("=" * 70)
    print()
    print("NOTE: This is portfolio-effect evaluation ONLY.")
    print("      It is NOT a final business recommendation.")
    print("      Scoring, ranking, and planning are deferred to Phase 2C–2E.")
    print()

    # ======================================================================
    # E001 -- quality_prerequisite
    # ======================================================================
    e001_base = next(e for e in result_base.effects if e.effect_id == "E001")
    e001_all = next(e for e in result_all.effects if e.effect_id == "E001")

    print(SEP)
    print("E001  quality_prerequisite")
    print(f"  Trigger : {e001_base.trigger_work_item_id}")
    print(f"  Targets : {', '.join(e001_base.targets)}")
    print()
    print("  [BASE -- trigger NOT satisfied]")
    risk_base = [w for w in e001_base.warnings if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_RISK]
    for w in risk_base:
        print(f"    -> {w.target_id}: ELEVATED RISK  (quantitative_impact_known=False)")
    print()
    print("  [ALL-TRIGGERS -- trigger satisfied]")
    sat_all = [w for w in e001_all.warnings if w.code == PortfolioEffectCode.QUALITY_PREREQUISITE_SATISFIED]
    for w in sat_all:
        print(f"    -> {w.target_id}: NORMAL RISK  (prerequisite completed)")
    print()

    # ======================================================================
    # E002 -- hours_reduction (deterministic)
    # ======================================================================
    e002_base = next(e for e in result_base.effects if e.effect_id == "E002")
    e002_all = next(e for e in result_all.effects if e.effect_id == "E002")
    tgt_id = e002_base.targets[0]  # "W015"

    print(SEP)
    print("E002  hours_reduction  (deterministic)")
    print(f"  Trigger : {e002_base.trigger_work_item_id}")
    print(f"  Target  : {tgt_id}")
    print(f"  Reduction: {e002_base.effect_id}")
    print()
    # Get reduction fraction from warning details
    w002_detail = next(
        (w.details for w in e002_all.warnings if w.code == PortfolioEffectCode.HOURS_REDUCTION_APPLIED),
        None
    )
    bh = base_hours.get(tgt_id, 0)
    print(f"  [BASE -- trigger NOT satisfied]")
    print(f"    Base hours      : {bh:.1f}h")
    print(f"    Effective hours : {bh:.1f}h  (unchanged, trigger not satisfied)")
    print()
    print(f"  [ALL-TRIGGERS -- trigger satisfied]")
    if w002_detail:
        print(f"    Base hours      : {w002_detail['base_required_hours']:.1f}h")
        print(f"    Reduction       : {w002_detail['reduction_fraction']*100:.0f}%")
        print(f"    Effective hours : {w002_detail['effective_required_hours']:.1f}h")
    print()

    # ======================================================================
    # E003 -- future_hours_reduction (probabilistic)
    # ======================================================================
    e003_base = next(e for e in result_base.effects if e.effect_id == "E003")
    e003_all = next(e for e in result_all.effects if e.effect_id == "E003")

    print(SEP)
    print("E003  future_hours_reduction  (probabilistic)")
    print(f"  Trigger : {e003_base.trigger_work_item_id}")
    print(f"  Targets : {', '.join(e003_base.targets)}")
    print()
    print("  [BASE -- trigger NOT satisfied]")
    for tgt in e003_base.targets:
        bh = base_hours.get(tgt, 0)
        print(f"    {tgt}: success={bh:.1f}h  downside={bh:.1f}h  (no impact)")
    print()
    print("  [ALL-TRIGGERS -- trigger satisfied]")
    for tgt in e003_all.targets:
        state = result_all.work_item_states.get(tgt)
        if state and state.probabilistic_hours:
            ph = state.probabilistic_hours
            print(f"    {tgt}:")
            print(f"      probability             : {ph.probability}")
            print(f"      impact_fraction         : {ph.impact_fraction}")
            print(f"      expected_impact_fraction: {ph.expected_impact_fraction:.3f}  (= {ph.probability}×{ph.impact_fraction})")
            print(f"      success_case_hours      : {ph.success_case_hours:.1f}h")
            print(f"      downside_case_hours     : {ph.downside_case_hours:.1f}h  (base, unchanged)")
            print(f"      committed plan hours    : {state.effective_required_hours:.1f}h  (base, NOT expected reduction)")
    print()

    # ======================================================================
    # E004 -- commercial_option_unlock
    # ======================================================================
    e004_base = next(e for e in result_base.effects if e.effect_id == "E004")
    e004_all = next(e for e in result_all.effects if e.effect_id == "E004")
    opt_id = e004_base.targets[0]  # "W007-B"

    print(SEP)
    print("E004  commercial_option_unlock")
    print(f"  Trigger : {e004_base.trigger_work_item_id}")
    print(f"  Option  : {opt_id}")
    print()
    s_base = result_base.commercial_option_states.get(opt_id)
    s_all = result_all.commercial_option_states.get(opt_id)
    print(f"  [BASE -- trigger NOT satisfied]")
    if s_base:
        print(f"    {opt_id}: available={s_base.available}  reason={[c.value for c in s_base.reason_codes]}")
    print()
    print(f"  [ALL-TRIGGERS -- trigger satisfied]")
    if s_all:
        print(f"    {opt_id}: available={s_all.available}  reason={[c.value for c in s_all.reason_codes]}")
    print()
    print("  (Ranking/selection deferred to Phase 2C)")
    print()

    # ======================================================================
    # E005 -- cash_inflow (probabilistic)
    # ======================================================================
    e005_base = next(e for e in result_base.effects if e.effect_id == "E005")
    e005_all = next(e for e in result_all.effects if e.effect_id == "E005")

    print(SEP)
    print("E005  cash_inflow  (probabilistic)")
    print(f"  Trigger : {e005_base.trigger_work_item_id}")
    print()
    print("  [BASE -- trigger NOT satisfied]")
    ce_base = result_base.cash_effects[0] if result_base.cash_effects else None
    if ce_base:
        print(f"    trigger_satisfied          : {ce_base.trigger_satisfied}")
        print(f"    expected_cash_inflow_jpy   : {fmt_jpy(ce_base.expected_cash_inflow_jpy)}")
        print(f"    success_case_cash          : {fmt_jpy(ce_base.success_case_cash_inflow_jpy)}")
        print(f"    downside_case_cash         : {fmt_jpy(ce_base.downside_case_cash_inflow_jpy)}")
    print()
    print("  [ALL-TRIGGERS -- trigger satisfied]")
    ce_all = result_all.cash_effects[0] if result_all.cash_effects else None
    if ce_all:
        print(f"    trigger_satisfied          : {ce_all.trigger_satisfied}")
        print(f"    probability                : {ce_all.probability}")
        print(f"    cash_inflow_jpy (declared) : {fmt_jpy(ce_all.cash_inflow_jpy)}")
        print(f"    expected_cash_inflow_jpy   : {fmt_jpy(ce_all.expected_cash_inflow_jpy)}")
        print(f"    success_case_cash          : {fmt_jpy(ce_all.success_case_cash_inflow_jpy)}")
        print(f"    downside_case_cash         : {fmt_jpy(ce_all.downside_case_cash_inflow_jpy)}")
    print()
    print("  (Cash-flow buffer simulation deferred to Phase 2F)")
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Portfolio effects declared : {len(ds.portfolio_effects)}")
    print(f"  Effects evaluated          : {len(result_base.effects)}")
    print(f"  Total warnings (base)      : {len(result_base.warnings)}")
    print()
    print("  Effect types handled:")
    for eff in result_base.effects:
        print(f"    {eff.effect_id}: {eff.effect_type}  "
              f"(deterministic={eff.deterministic}, trigger_base={eff.trigger_satisfied})")
    print()
    print("  Work items with derived states (base):", list(result_base.work_item_states.keys()))
    print("  Commercial options with lock states (base):", list(result_base.commercial_option_states.keys()))
    print()


if __name__ == "__main__":
    main()
