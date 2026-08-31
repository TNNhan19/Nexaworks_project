"""Thin FastAPI adapter for Phase 2G Final Validation Engine."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.decision_engine.cash_flow import CashFlowResult, CashFlowSimulator
from app.decision_engine.final_validation import FinalDecisionResult, FinalValidationEngine
from app.decision_engine.planner import PlanResult, PlannerEngine
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/final-decision", tags=["final-decision"])
BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


class FinalDecisionRequest(BaseModel):
    plan: PlanResult | None = None
    cash_result: CashFlowResult | None = None
    completed_work_item_ids: list[str] = Field(default_factory=list)


def _dataset():
    try:
        return load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc


@router.post("", response_model=FinalDecisionResult)
def get_final_decision(request: FinalDecisionRequest) -> FinalDecisionResult:
    """Produce the integrated final decision result (Phase 2G).

    If ``plan`` is not supplied, runs Phase 2E planner on the canonical dataset.
    If ``cash_result`` is not supplied, runs Phase 2F cash simulator on the plan.
    Phase 2G validates and explains only — it never replans or rescores.
    """
    dataset = _dataset()
    completed_ids = frozenset(request.completed_work_item_ids)
    plan = request.plan or PlannerEngine().plan(dataset, completed_work_item_ids=completed_ids)
    cash_result = request.cash_result or CashFlowSimulator().simulate(dataset, plan)
    return FinalValidationEngine().validate(dataset, plan, cash_result)
