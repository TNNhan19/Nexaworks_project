from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.scenarios.errors import (
    InvalidRunStateError, RunNotFoundError, ScenarioNotFoundError, ScenarioValidationError,
)
from app.scenarios.models import (
    RunComparison, Scenario, ScenarioCreate, ScenarioPatch, ScenarioRun,
)
from app.scenarios.repository import SQLiteScenarioRepository
from app.scenarios.service import ScenarioService

router = APIRouter(prefix="/api/v1", tags=["scenarios"])
ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = ROOT / "data" / "candidate_dataset.json"
SCHEMA_PATH = ROOT / "data" / "candidate_dataset.schema.json"


def get_scenario_service() -> ScenarioService:
    database_path = Path(
        os.environ.get("NEXAWORKS_DB_PATH", ROOT / "runtime" / "scenarios.sqlite3")
    )
    return ScenarioService(SQLiteScenarioRepository(database_path), DATASET_PATH, SCHEMA_PATH)


def _error(exc, status_code: int) -> HTTPException:
    detail = {"code": exc.code, "message": exc.message}
    if exc.errors:
        detail["errors"] = exc.errors
    return HTTPException(status_code=status_code, detail=detail)


@router.get("/baseline/summary")
def baseline_summary(service: ScenarioService = Depends(get_scenario_service)) -> dict:
    return service.baseline_summary()


@router.get("/scenarios", response_model=list[Scenario])
def list_scenarios(service: ScenarioService = Depends(get_scenario_service)):
    return service.list()


@router.post("/scenarios", response_model=Scenario, status_code=status.HTTP_201_CREATED)
def create_scenario(request: ScenarioCreate,
                    service: ScenarioService = Depends(get_scenario_service)):
    try:
        return service.create(request)
    except ScenarioValidationError as exc:
        raise _error(exc, 400) from exc


@router.get("/scenarios/{scenario_id}", response_model=Scenario)
def get_scenario(scenario_id: str, service: ScenarioService = Depends(get_scenario_service)):
    try:
        return service.get(scenario_id)
    except ScenarioNotFoundError as exc:
        raise _error(exc, 404) from exc


@router.patch("/scenarios/{scenario_id}", response_model=Scenario)
def update_scenario(scenario_id: str, request: ScenarioPatch,
                    service: ScenarioService = Depends(get_scenario_service)):
    try:
        return service.update(scenario_id, request)
    except ScenarioNotFoundError as exc:
        raise _error(exc, 404) from exc
    except ScenarioValidationError as exc:
        raise _error(exc, 400) from exc


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: str,
                    service: ScenarioService = Depends(get_scenario_service)):
    try:
        service.delete(scenario_id)
    except ScenarioNotFoundError as exc:
        raise _error(exc, 404) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/scenarios/{scenario_id}/run", response_model=ScenarioRun, status_code=201)
def run_scenario(scenario_id: str,
                 service: ScenarioService = Depends(get_scenario_service)):
    try:
        return service.run(scenario_id)
    except ScenarioNotFoundError as exc:
        raise _error(exc, 404) from exc
    except ScenarioValidationError as exc:
        raise _error(exc, 400) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "code": "PIPELINE_EXECUTION_FAILED", "message": "Scenario run failed",
        }) from exc


@router.get("/scenarios/{scenario_id}/runs", response_model=list[ScenarioRun])
def list_scenario_runs(scenario_id: str,
                       service: ScenarioService = Depends(get_scenario_service)):
    try:
        return service.list_runs(scenario_id)
    except ScenarioNotFoundError as exc:
        raise _error(exc, 404) from exc


@router.get("/runs/compare", response_model=RunComparison)
def compare_scenario_runs(run_a_id: str = Query(), run_b_id: str = Query(),
                          service: ScenarioService = Depends(get_scenario_service)):
    try:
        return service.compare(run_a_id, run_b_id)
    except RunNotFoundError as exc:
        raise _error(exc, 404) from exc
    except InvalidRunStateError as exc:
        raise _error(exc, 409) from exc


@router.get("/runs/{run_id}", response_model=ScenarioRun)
def get_scenario_run(run_id: str,
                     service: ScenarioService = Depends(get_scenario_service)):
    try:
        return service.get_run(run_id)
    except RunNotFoundError as exc:
        raise _error(exc, 404) from exc
