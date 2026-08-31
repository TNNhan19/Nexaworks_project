from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError

from app.domain.models import CandidateDataset
from app.services.dataset_loader import validate_references

from .errors import ScenarioValidationError
from .models import ScenarioOverrides


def _changes(model, id_field: str | None = None) -> dict:
    excluded = {id_field} if id_field else set()
    return {
        key: value
        for key, value in model.model_dump(mode="json", exclude_unset=True).items()
        if key not in excluded
    }


def apply_overrides(dataset: CandidateDataset, overrides: ScenarioOverrides) -> CandidateDataset:
    """Apply overrides to an isolated copy and rerun domain/reference validation."""
    raw = deepcopy(dataset.model_dump(mode="json"))
    if overrides.company is not None:
        raw["company"].update(_changes(overrides.company))
    # Domain records use `id`; request models deliberately use descriptive target keys.
    _apply_named(raw["people"], overrides.people, "id", "person_id", "person")
    _apply_named(raw["work_items"], overrides.work_items, "id", "work_item_id", "work item")
    _apply_named(
        raw["commercial_options"], overrides.commercial_options,
        "option_id", "option_id", "commercial option",
    )
    _apply_named(raw["shared_resources"], overrides.resources, "id", "resource_id", "resource")
    try:
        effective = CandidateDataset.model_validate(raw)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in exc.errors()
        ]
        raise ScenarioValidationError("Effective dataset is invalid", errors) from exc
    issues = validate_references(effective)
    if issues:
        raise ScenarioValidationError("Effective dataset has invalid references", issues)
    return effective


def _apply_named(
    raw_items: list[dict], overrides: list, raw_id: str, override_id: str, label: str
) -> None:
    index = {item[raw_id]: item for item in raw_items}
    for override in overrides:
        target = getattr(override, override_id)
        if target not in index:
            raise ScenarioValidationError(
                f"Unknown {label} override target: {target}",
                [f"{label} {target} does not exist in the baseline"],
            )
        index[target].update(_changes(override, override_id))
