from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.api.feasibility import router as feasibility_router
from app.api.commercial import router as commercial_router
from app.api.portfolio import router as portfolio_router
from app.api.scoring import router as scoring_router
from app.api.planner import router as planner_router
from app.api.cash_flow import router as cash_flow_router
from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS
from app.services.baseline_summary import summary_as_dict
from app.services.dataset_loader import DatasetValidationError, load_dataset

BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"

app = FastAPI(title="NexaWorks Decision Support API", version="0.5.0")

app.include_router(feasibility_router)
app.include_router(portfolio_router)
app.include_router(commercial_router)
app.include_router(scoring_router)
app.include_router(planner_router)
app.include_router(cash_flow_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/assumptions")
def assumptions() -> dict:
    return DEFAULT_ASSUMPTIONS.model_dump()


@app.get("/api/v1/dataset/summary")
def dataset_summary() -> dict:
    try:
        dataset = load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    return summary_as_dict(dataset)
