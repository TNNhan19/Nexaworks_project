"""Read-only data intake and staged planning orchestration.

The adapter validates a canonical-format JSON payload, then delegates every
business decision to the existing Decision Engine. It stores no dataset and
never mutates the canonical baseline.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from app.domain.models import CandidateDataset
from app.scenarios.pipeline import DecisionPipelineService
from app.services.baseline_summary import summary_as_dict
from app.services.dataset_loader import (
    DatasetValidationError,
    load_dataset,
    read_json,
    validate_json_schema,
    validate_references,
)

router = APIRouter(prefix="/api/v1/planning", tags=["planning"])
BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


class PlanningDatasetRequest(BaseModel):
    dataset: dict[str, Any] | None = None
    completed_work_item_ids: list[str] = Field(default_factory=list)


def _validation_error(errors: list[str]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": "PLANNING_DATA_INVALID",
            "message": "Planning data did not pass validation.",
            "errors": errors,
        },
    )


def _dataset(payload: dict[str, Any] | None) -> CandidateDataset:
    if payload is None:
        try:
            return load_dataset(DATASET_PATH, SCHEMA_PATH)
        except DatasetValidationError as exc:
            raise _validation_error(exc.errors) from exc

    issues = validate_json_schema(payload, read_json(SCHEMA_PATH))
    if issues:
        raise _validation_error(issues)
    try:
        dataset = CandidateDataset.model_validate(payload)
    except PydanticValidationError as exc:
        errors = [
            f"{'.'.join(str(item) for item in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
        raise _validation_error(errors) from exc
    reference_issues = validate_references(dataset)
    if reference_issues:
        raise _validation_error(reference_issues)
    return dataset


def _summary(dataset: CandidateDataset) -> dict[str, Any]:
    return {
        **summary_as_dict(dataset),
        "dataset_id": dataset.metadata.dataset_id,
        "dataset_version": dataset.metadata.version,
        "planning_start": dataset.metadata.planning_start,
        "planning_end": dataset.metadata.planning_end,
        "currency": dataset.metadata.currency,
        "starting_cash_jpy": dataset.company.starting_cash_jpy,
        "minimum_cash_buffer_jpy": dataset.company.minimum_cash_buffer_jpy,
    }


def _catalog(dataset: CandidateDataset) -> dict[str, Any]:
    return {
        "summary": _summary(dataset),
        "company": dataset.company.model_dump(mode="json"),
        "work_items": [item.model_dump(mode="json") for item in dataset.work_items],
        "people": [item.model_dump(mode="json") for item in dataset.people],
        "customers": [item.model_dump(mode="json") for item in dataset.customers],
        "shared_resources": [
            item.model_dump(mode="json") for item in dataset.shared_resources
        ],
        "commercial_options": [
            item.model_dump(mode="json") for item in dataset.commercial_options
        ],
        "portfolio_effects": [
            item.model_dump(mode="json") for item in dataset.portfolio_effects
        ],
    }


@router.get("/sample")
def sample_planning_data() -> dict[str, Any]:
    """Return the canonical dataset as display-safe planning facts."""
    return _catalog(_dataset(None))


@router.post("/review")
def review_planning_data(request: PlanningDatasetRequest) -> dict[str, Any]:
    """Validate and summarize a canonical-format JSON dataset without analysis."""
    return _catalog(_dataset(request.dataset))


@router.post("/analyze")
def analyze_planning_data(request: PlanningDatasetRequest) -> dict[str, Any]:
    """Run feasibility, portfolio, commercial, and scoring only."""
    dataset = _dataset(request.dataset)
    return DecisionPipelineService().analyze(
        dataset,
        completed_work_item_ids=frozenset(request.completed_work_item_ids),
    )


@router.post("/generate")
def generate_planning_data(request: PlanningDatasetRequest) -> dict[str, Any]:
    """Generate the operational plan and validate cash using existing engines."""
    dataset = _dataset(request.dataset)
    return DecisionPipelineService().run(
        dataset,
        completed_work_item_ids=frozenset(request.completed_work_item_ids),
    )
