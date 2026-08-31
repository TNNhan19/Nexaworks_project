"""Thin FastAPI adapter for the framework-independent Phase 2E planner."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.decision_engine.planner import PlanResult, PlannerEngine
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/plan", tags=["planner"])
BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


class PlanRequest(BaseModel):
    completed_work_item_ids: list[str] = Field(default_factory=list)


def _dataset():
    try:
        return load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc


@router.get("", response_model=PlanResult)
def get_plan() -> PlanResult:
    return PlannerEngine().plan(_dataset())


@router.post("", response_model=PlanResult)
def create_plan(request: PlanRequest) -> PlanResult:
    return PlannerEngine().plan(
        _dataset(), completed_work_item_ids=frozenset(request.completed_work_item_ids)
    )
