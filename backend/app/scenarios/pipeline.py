from __future__ import annotations

from typing import Any

from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS, AssumptionRegistry
from app.decision_engine.cash_flow import CashFlowSimulator
from app.decision_engine.commercial import CommercialEvaluationEngine
from app.decision_engine.feasibility import FeasibilityEngine
from app.decision_engine.final_validation import FinalValidationEngine
from app.decision_engine.planner import PlannerEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine, PortfolioEvaluationContext
from app.decision_engine.scoring import ScoringEngine
from app.domain.models import CandidateDataset


def _json(value) -> Any:
    if isinstance(value, list):
        return [item.model_dump(mode="json") for item in value]
    return value.model_dump(mode="json")


class DecisionPipelineService:
    """Application orchestration only; all business decisions remain in Phase 2 engines."""

    def __init__(self, assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS):
        self.assumptions = assumptions

    def run(
        self,
        dataset: CandidateDataset,
        completed_work_item_ids: frozenset[str] = frozenset(),
    ) -> dict[str, Any]:
        context = PortfolioEvaluationContext(
            completed_work_item_ids=completed_work_item_ids,
            planning_date=dataset.metadata.planning_start,
            all_work_item_ids=frozenset(item.id for item in dataset.work_items),
            all_commercial_option_ids=frozenset(
                item.option_id for item in dataset.commercial_options
            ),
        )
        portfolio = PortfolioEffectsEngine().evaluate(dataset, context)
        effective_hours = {
            item.id: portfolio.get_effective_hours(item.id, item.required_hours)
            for item in dataset.work_items
        }
        feasibility = FeasibilityEngine(self.assumptions).check_all(
            dataset,
            completed_ids=completed_work_item_ids,
            effective_hours_override=effective_hours,
        )
        commercial = CommercialEvaluationEngine().evaluate(
            dataset, portfolio, completed_ids=completed_work_item_ids
        )
        scoring = ScoringEngine(self.assumptions).evaluate(
            dataset,
            portfolio,
            commercial,
            feasibility_results=feasibility,
            completed_ids=completed_work_item_ids,
        )
        plan = PlannerEngine(self.assumptions).plan(
            dataset,
            completed_work_item_ids=completed_work_item_ids,
            scoring_reference=scoring.normalization_reference,
        )
        cash_flow = CashFlowSimulator(self.assumptions).simulate(dataset, plan)
        final_decision = FinalValidationEngine(self.assumptions).validate(
            dataset, plan, cash_flow
        )
        return {
            "feasibility": _json(feasibility),
            "portfolio": _json(portfolio),
            "commercial": _json(commercial),
            "scoring": _json(scoring),
            "plan": _json(plan),
            "cash_flow": _json(cash_flow),
            "final_decision": _json(final_decision),
        }
