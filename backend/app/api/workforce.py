"""Read-only workforce API router providing employee master data."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.domain.models import LocalizedText
from app.services.dataset_loader import DatasetValidationError, load_dataset

router = APIRouter(prefix="/api/v1/workforce", tags=["workforce"])
BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "data" / "candidate_dataset.json"
SCHEMA_PATH = BASE_DIR / "data" / "candidate_dataset.schema.json"


def _dataset():
    try:
        return load_dataset(DATASET_PATH, SCHEMA_PATH)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc


@router.get("/people")
def get_people() -> list[dict[str, Any]]:
    """Return employee master data from the baseline dataset."""
    dataset = _dataset()
    return [
        {
            "id": person.id,
            "person_id": person.id,
            "name": person.name,
            "role": person.role.model_dump(mode="json")
            if isinstance(person.role, LocalizedText)
            else person.role,
            "capacity_hours": person.capacity_hours,
            "hourly_cost_jpy": person.hourly_cost_jpy,
            "skills": person.skills,
            "languages": person.languages,
            "unavailable_ranges": [
                {"start": r.start.isoformat(), "end": r.end.isoformat()}
                for r in person.unavailable_ranges
            ],
        }
        for person in dataset.people
    ]
