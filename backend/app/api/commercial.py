"""Thin FastAPI adapter for framework-independent Phase 2C evaluation."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.decision_engine.commercial import CommercialEvaluationEngine
from app.decision_engine.commercial.models import CommercialEvaluationResult, OpportunityEvaluation
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/commercial", tags=["commercial"])
BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


def _evaluate() -> CommercialEvaluationResult:
    try:
        dataset = load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    engine = CommercialEvaluationEngine()
    portfolio_result = engine.build_portfolio_context(dataset)
    return engine.evaluate(dataset, portfolio_result)


@router.get("", response_model=CommercialEvaluationResult)
def commercial_all() -> CommercialEvaluationResult:
    return _evaluate()


@router.get("/{work_item_id}", response_model=OpportunityEvaluation)
def commercial_one(work_item_id: str) -> OpportunityEvaluation:
    opportunity = _evaluate().get_opportunity(work_item_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail=f"Commercial opportunity '{work_item_id}' not found.")
    return opportunity
