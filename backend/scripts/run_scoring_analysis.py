"""Development report for canonical Phase 2D business-value scoring."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.decision_engine.commercial import CommercialEvaluationEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.scoring import ScoringEngine, SelectionStatus
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    dataset = load_dataset(
        ROOT / "data/candidate_dataset.json",
        ROOT / "data/candidate_dataset.schema.json",
    )
    portfolio_engine = PortfolioEffectsEngine()
    portfolio = portfolio_engine.evaluate(
        dataset, portfolio_engine.build_context_from_dataset(dataset)
    )
    commercial = CommercialEvaluationEngine().evaluate(dataset, portfolio)
    result = ScoringEngine().evaluate(dataset, portfolio, commercial)

    print("Configured BALANCED V1 weights:", result.configured_weights.model_dump())
    print("Reference usage:", result.reference_usage.value)
    print()
    for status in SelectionStatus:
        candidates = sorted(
            (candidate for candidate in result.candidates if candidate.selection_status == status),
            key=lambda candidate: (-float(candidate.business_value_score or 0), candidate.action_id),
        )
        if not candidates:
            continue
        print(f"=== {status.value} ({len(candidates)}) ===")
        for candidate in candidates:
            contributions = ", ".join(
                f"{component.name.value}={component.weighted_contribution:.4f}"
                for component in candidate.components
                if component.applicable
            )
            warning_codes = ",".join(warning.code.value for warning in candidate.warnings) or "-"
            print(
                f"{candidate.action_id} | {candidate.action_type.value} | "
                f"work={candidate.work_item_id} | mandatory={candidate.mandatory} | "
                f"score={candidate.business_value_score:.2f} | "
                f"contributions[{contributions}] | warnings={warning_codes}"
            )
        print()
    print("Phase 2D ranks business value only.")
    print("Phase 2E Planner makes the final constrained selection.")


if __name__ == "__main__":
    main()
