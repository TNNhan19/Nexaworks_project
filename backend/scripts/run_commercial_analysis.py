"""Print the canonical Phase 2C descriptive commercial report."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.decision_engine.commercial import CommercialEvaluationEngine
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]


def money(value):
    return "N/A" if value is None else f"{value:,.0f}"


def main() -> None:
    dataset = load_dataset(
        ROOT / "data/candidate_dataset.json",
        ROOT / "data/candidate_dataset.schema.json",
    )
    engine = CommercialEvaluationEngine()
    result = engine.evaluate(dataset, engine.build_portfolio_context(dataset))
    for opportunity in result.opportunities:
        for option in opportunity.options:
            print(
                f"{opportunity.work_item_id} | {option.option_id} | {option.availability.value} | "
                f"price={money(option.price_jpy)} | cost={money(option.direct_cost_jpy)} | "
                f"gross_margin={money(option.gross_margin_jpy)} | p={option.win_probability} | "
                f"expected_revenue={money(option.expected_revenue_jpy)} | "
                f"expected_margin={money(option.expected_margin_jpy)} | "
                f"follow_on={money(option.follow_on_value_jpy)} | "
                f"delivery_hours={option.delivery_hours} | "
                f"total_committed_hours_if_won={option.total_committed_hours_if_won} | "
                f"deliverability={option.deliverability.value}"
            )
    print("Commercial Evaluation is descriptive and contains canonical options only.")
    print("Phase 2D scores real options; final SELECT_OPTION or NO_BID belongs to Phase 2E Planner.")


if __name__ == "__main__":
    main()
