"""Thin FastAPI adapter for framework-independent Phase 2D scoring."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.decision_engine.commercial import CommercialEvaluationEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.scoring import ScoredCandidate, ScoringEngine, ScoringResult
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/scoring", tags=["scoring"])
BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


def _evaluate() -> ScoringResult:
    try:
        dataset = load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    portfolio_engine = PortfolioEffectsEngine()
    context = portfolio_engine.build_context_from_dataset(dataset)
    portfolio = portfolio_engine.evaluate(dataset, context)
    commercial = CommercialEvaluationEngine().evaluate(dataset, portfolio)
    return ScoringEngine().evaluate(dataset, portfolio, commercial)


@router.get("", response_model=ScoringResult)
def scoring_all() -> ScoringResult:
    return _evaluate()


@router.get("/{action_id}", response_model=ScoredCandidate)
def scoring_one(action_id: str) -> ScoredCandidate:
    candidate = _evaluate().get_candidate(action_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Scoring action '{action_id}' not found.")
    return candidate
