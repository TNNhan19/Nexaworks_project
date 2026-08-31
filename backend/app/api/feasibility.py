"""FastAPI adapter for the Feasibility Engine.

This module is a thin adapter only — all business logic lives in the
Decision Engine (app.decision_engine.feasibility).  The API layer:
  - loads the dataset
  - calls the engine
  - serialises the result

The engine has no dependency on FastAPI.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS
from app.decision_engine.feasibility import FeasibilityEngine
from app.decision_engine.feasibility.models import FeasibilityResult
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/feasibility", tags=["feasibility"])

BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


def _load() -> "app.domain.models.CandidateDataset":  # type: ignore[name-defined]
    try:
        return load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc


@router.get("", response_model=list[FeasibilityResult])
def feasibility_all() -> list[FeasibilityResult]:
    """Run the Feasibility Engine against all work items in the canonical dataset.

    This is a **development / analysis endpoint**.  It uses the default assumption
    registry and treats all work items as not-yet-completed (most conservative base).

    Returns a list of FeasibilityResult, one per work item.
    """
    dataset = _load()
    engine = FeasibilityEngine(DEFAULT_ASSUMPTIONS)
    return engine.check_all(dataset)


@router.get("/{work_item_id}", response_model=FeasibilityResult)
def feasibility_single(work_item_id: str) -> FeasibilityResult:
    """Run the Feasibility Engine for a single work item.

    Returns 404 if the work item ID is not found in the dataset.
    """
    dataset = _load()
    work_item = next(
        (w for w in dataset.work_items if w.id == work_item_id), None
    )
    if work_item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Work item '{work_item_id}' not found in dataset.",
        )
    engine = FeasibilityEngine(DEFAULT_ASSUMPTIONS)
    return engine.check_work_item(work_item, dataset)
