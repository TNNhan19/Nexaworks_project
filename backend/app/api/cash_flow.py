"""Thin FastAPI adapter for framework-independent Phase 2F cash simulation."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.decision_engine.cash_flow import CashFlowResult, CashFlowSimulator
from app.decision_engine.planner import PlanResult, PlannerEngine
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/cash-flow", tags=["cash-flow"])
BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


class CashFlowRequest(BaseModel):
    plan: PlanResult | None = None
    completed_work_item_ids: list[str] = Field(default_factory=list)


def _dataset():
    try:
        return load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc


@router.post("", response_model=CashFlowResult)
def simulate_cash_flow(request: CashFlowRequest) -> CashFlowResult:
    dataset = _dataset()
    plan = request.plan or PlannerEngine().plan(
        dataset,
        completed_work_item_ids=frozenset(request.completed_work_item_ids),
    )
    return CashFlowSimulator().simulate(dataset, plan)
