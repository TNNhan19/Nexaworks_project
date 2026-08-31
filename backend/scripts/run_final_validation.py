"""Phase 2G canonical final decision report.

Runs the full Phase 2E planner + Phase 2F cash simulator + Phase 2G final
validation on the canonical dataset and prints a structured ASCII report.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.decision_engine.cash_flow import CashFlowSimulator
from app.decision_engine.final_validation import (
    FinalValidationEngine,
    ExplanationCode,
    FindingSeverity,
    OperationalStatus,
    OverallStatus,
)
from app.decision_engine.planner import PlannerEngine
from app.services.dataset_loader import load_dataset

ROOT = BACKEND.parent
DATA = ROOT / "data"

SEP = "=" * 72
SB = "-" * 72


def jpy(v: int | None) -> str:
    if v is None:
        return "N/A"
    sign = "-" if v < 0 else ""
    return f"JPY {sign}{abs(v):,}"


def main() -> None:
    dataset = load_dataset(
        DATA / "candidate_dataset.json",
        DATA / "candidate_dataset.schema.json",
    )
    plan = PlannerEngine().plan(dataset)
    cash = CashFlowSimulator().simulate(dataset, plan)
    result = FinalValidationEngine().validate(dataset, plan, cash)

    es = result.executive_summary
    ms = result.mandatory_summary
    cs = result.capacity_summary
    rs = result.resource_summary
    cash_s = result.cash_summary

    print(SEP)
    print("PHASE 2G -- FINAL DECISION REPORT (CANONICAL DATASET)")
    print(SEP)

    # A/B/C: Statuses
    print()
    print("A/B/C  STATUS")
    print(SB)
    print(f"  Overall status      : {result.overall_status.value}")
    print(f"  Operational status  : {result.operational_status.value}")
    print(f"  Financial status    : {result.financial_status.value}")

    # D: Counts
    print()
    print("D  COUNTS")
    print(SB)
    print(f"  Selected actions    : {es.selected_count}")
    print(f"  Delayed actions     : {es.delayed_count}")
    print(f"  NO-BID opportunities: {es.no_bid_count}")

    # E: Mandatory
    print()
    print("E  MANDATORY OUTCOME")
    print(SB)
    print(f"  Total mandatory     : {ms.total_mandatory}")
    print(f"  Scheduled           : {ms.scheduled_count}")
    print(f"  Infeasible          : {ms.infeasible_count}")
    print(f"  Omitted             : {ms.omitted_count}")
    for outcome in ms.outcomes:
        status_str = (
            "SCHEDULED" if outcome.scheduled
            else "INFEASIBLE" if outcome.infeasible
            else "OMITTED"
        )
        cd = str(outcome.completion_date) if outcome.completion_date else "N/A"
        print(f"    {outcome.work_item_id:<12} {status_str:<12} completion={cd}")

    # F: Capacity / resource validity
    print()
    print("F  CAPACITY / RESOURCE VALIDITY")
    print(SB)
    print(f"  Total capacity      : {cs.total_capacity_hours:.1f} hrs")
    print(f"  Total used          : {cs.total_used_hours:.1f} hrs")
    print(f"  Total remaining     : {cs.total_remaining_hours:.1f} hrs")
    cap_violations = len(cs.violations)
    res_violations = len(rs.violations)
    print(f"  Capacity violations : {cap_violations}")
    print(f"  Resource violations : {res_violations}")
    print(f"  Resource summary:")
    for r in rs.resources:
        excl = " [exclusive]" if r.exclusive else ""
        print(f"    {r.resource_id:<12} used={r.used_hours:.1f}/{r.capacity_hours:.1f} hrs{excl}")

    # G: Cash
    print()
    print("G  CASH")
    print(SB)
    print(f"  Starting cash       : {jpy(cash_s.starting_cash_jpy)}")
    print(f"  Min buffer          : {jpy(cash_s.minimum_buffer_jpy)}")
    for sc in cash_s.scenarios:
        print(f"  [{sc.scenario}]")
        print(f"    Status            : {sc.status}")
        print(f"    Ending cash       : {jpy(sc.ending_cash_jpy)}")
        print(f"    Minimum cash      : {jpy(sc.minimum_cash_jpy)} on {sc.minimum_cash_date}")
        print(f"    Buffer breach     : {sc.first_buffer_breach_date or 'None'}")
        print(f"    Days below buffer : {sc.days_below_buffer}")
        print(f"    Negative cash     : {sc.negative_cash}")

    print()
    print("  Future receipts (outside horizon):")
    for fr in cash_s.future_receipts:
        print(f"    {str(fr.date):<12} {fr.source_id:<12} {fr.event_type:<35} {jpy(fr.expected_amount_jpy)}")
    if not cash_s.future_receipts:
        print("    (none)")

    # H: Main risks
    print()
    print("H  MAIN RISKS")
    print(SB)
    for risk_code in es.major_risks:
        print(f"  - {risk_code}")
    if not es.major_risks:
        print("  (none)")

    # I: Main strengths
    print()
    print("I  MAIN STRENGTHS")
    print(SB)
    for strength_code in es.major_strengths:
        print(f"  + {strength_code}")
    if not es.major_strengths:
        print("  (none)")

    # J: Decision explanations for key items
    ITEMS_TO_EXPLAIN = {"W001", "W006", "W007", "W012", "W021"}
    # Also match by action_id containing W012-A or W021
    print()
    print("J  DECISION EXPLANATIONS (W001 / W006 / W007 / W012-A / W021)")
    print(SB)
    seen_wids: set[str] = set()
    for dec_exp in result.decision_explanations:
        wid = dec_exp.work_item_id
        aid = dec_exp.action_id
        show = wid in ITEMS_TO_EXPLAIN or aid in {"W012-A", "W021"}
        if show and wid not in seen_wids:
            seen_wids.add(wid)
            print(f"  {wid} / {aid}")
            print(f"    decision   : {dec_exp.decision}")
            print(f"    reason_codes : {dec_exp.reason_codes}")
            for f in dec_exp.findings:
                sev = f.severity.value
                print(f"    [{sev}] {f.code.value} ({f.source_phase.value})")
                if f.evidence:
                    for k, v in list(f.evidence.items())[:4]:
                        print(f"           {k}: {v}")
            if dec_exp.details:
                cd = dec_exp.details.get("completion_date")
                sd = dec_exp.details.get("start_date")
                if sd or cd:
                    print(f"    schedule   : start={sd}  completion={cd}")
            print()

    # Critical issues summary
    print()
    print("CRITICAL ISSUES")
    print(SB)
    for issue in result.critical_issues:
        print(f"  [{issue.severity.value}] {issue.code.value} ({issue.source_phase.value})")
        for k, v in list(issue.evidence.items())[:3]:
            print(f"       {k}: {v}")

    print()
    print(SEP)
    print(f"TOTAL explanation records : {len(result.explanation_records)}")
    print(f"Critical/Error issues     : {len(result.critical_issues)}")
    print(f"Warnings                  : {len(result.warnings)}")
    print(SEP)


if __name__ == "__main__":
    main()
