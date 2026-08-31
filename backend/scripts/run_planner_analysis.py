"""Print the canonical Phase 2E development plan report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.decision_engine.planner import DecisionType, PlannerEngine
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    dataset = load_dataset(ROOT / "data/candidate_dataset.json", ROOT / "data/candidate_dataset.schema.json")
    result = PlannerEngine().plan(dataset)
    print(f"PLAN STATUS: {result.status.value}")
    print(f"SELECTED: {', '.join(result.selected_actions)}")
    print(f"DELAYED: {', '.join(result.delayed_actions)}")
    print(f"NO_BID: {', '.join(result.no_bid_opportunities)}")
    print(f"MANDATORY_INFEASIBLE: {', '.join(result.mandatory_infeasible) or 'none'}")
    print("\nDECISIONS")
    for decision in result.decisions:
        if decision.decision in {DecisionType.DO, DecisionType.SELECT_OPTION, DecisionType.NO_BID, DecisionType.MANDATORY_INFEASIBLE}:
            print(
                decision.work_item_id,
                decision.action_id,
                decision.decision.value,
                f"score={decision.business_value_score}",
                f"prerequisites={decision.prerequisite_ids}",
                f"reasons={[code.value for code in decision.reason_codes]}",
            )
    print("\nPERSON CAPACITY")
    for item in result.person_capacity:
        print(item.person_id, f"used={item.used_hours}", f"remaining={item.remaining_hours}")
    print("\nRESOURCE CAPACITY")
    for item in result.resource_capacity:
        print(item.resource_id, f"used={item.used_hours}", f"remaining={item.remaining_hours}")
    print("\nPhase 2E produces the operational plan.")
    print("Phase 2F must still validate cash-flow and minimum cash buffer.")


if __name__ == "__main__":
    main()
