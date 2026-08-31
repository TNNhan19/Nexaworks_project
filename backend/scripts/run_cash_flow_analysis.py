"""Canonical Phase 2F cash-flow development report."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.decision_engine.cash_flow import CashEventType, CashFlowSimulator
from app.decision_engine.planner import PlannerEngine
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    dataset = load_dataset(
        ROOT / "data" / "candidate_dataset.json",
        ROOT / "data" / "candidate_dataset.schema.json",
    )
    plan = PlannerEngine().plan(dataset)
    result = CashFlowSimulator().simulate(dataset, plan)
    print(f"OVERALL CASH STATUS: {result.overall_status.value}")
    print(f"OPERATIONAL PLAN STATUS: {result.operational_plan_status}")
    for scenario, item in result.scenarios.items():
        print(f"\n{scenario.value}")
        print(f"status={item.status.value}")
        print(f"starting_cash={result.starting_cash_jpy}")
        print(f"cash_in={item.total_cash_in_jpy}")
        print(f"cash_out={item.total_cash_out_jpy}")
        print(f"minimum_cash={item.minimum_cash_jpy} on {item.minimum_cash_date}")
        print(f"ending_cash={item.ending_cash_jpy}")
        print(f"first_buffer_breach={item.first_buffer_breach_date}")
        print(f"days_below_buffer={item.days_below_buffer}")
        print(f"negative_days={len(item.negative_cash_dates)}")
        print(f"event_totals={item.event_totals_jpy}")
        for event in [*item.in_horizon_events, *item.future_events]:
            if event.source_id in {"W001", "W002", "W012-A", "E005"}:
                print(
                    event.event_type.value,
                    event.source_id,
                    event.date,
                    event.amount_jpy,
                    "future" if event.outside_horizon else "in_horizon",
                )
    print("\nPhase 2F validates cash-flow only.")
    print("Phase 2G performs final integrated validation and explanation.")


if __name__ == "__main__":
    main()
