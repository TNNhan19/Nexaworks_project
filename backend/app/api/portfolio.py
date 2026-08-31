"""FastAPI adapter for the Portfolio Effects Engine.

Thin adapter only — all business logic lives in
app.decision_engine.portfolio.  This module handles:
  - Loading the dataset
  - Building the evaluation context
  - Serialising the result

The engine has no dependency on FastAPI.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.decision_engine.portfolio import PortfolioEffectsEngine, PortfolioEffectsResult
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


def _load():
    try:
        return load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc


@router.get("", response_model=PortfolioEffectsResult)
def portfolio_effects_base() -> PortfolioEffectsResult:
    """Run the Portfolio Effects Engine with no completed work items (base state).

    Returns the structured PortfolioEffectsResult showing all effect evaluations
    and derived indexes.  This is a development/analysis endpoint.

    To simulate scenarios where some work items are completed, use the
    Portfolio Effects Engine directly from Python.
    """
    dataset = _load()
    engine = PortfolioEffectsEngine()
    context = PortfolioEffectsEngine.build_context_from_dataset(dataset)
    return engine.evaluate(dataset, context)
