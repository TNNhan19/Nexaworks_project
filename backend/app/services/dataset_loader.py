from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError as PydanticValidationError

from app.domain.models import CandidateDataset


class DatasetValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Dataset validation failed: " + "; ".join(errors))


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_json_schema(raw: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    issues: list[str] = []
    for error in sorted(validator.iter_errors(raw), key=lambda e: list(e.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        issues.append(f"{location}: {error.message}")
    return issues


def load_dataset(
    dataset_path: str | Path,
    schema_path: str | Path | None = None,
) -> CandidateDataset:
    raw = read_json(dataset_path)

    issues: list[str] = []
    if schema_path is not None:
        issues.extend(validate_json_schema(raw, read_json(schema_path)))

    if issues:
        raise DatasetValidationError(issues)

    try:
        dataset = CandidateDataset.model_validate(raw)
    except PydanticValidationError as exc:
        formatted = [
            f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        raise DatasetValidationError(formatted) from exc

    semantic_issues = validate_references(dataset)
    if semantic_issues:
        raise DatasetValidationError(semantic_issues)
    return dataset


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def validate_references(dataset: CandidateDataset) -> list[str]:
    """Validate cross-entity references and obvious contradictions.

    This layer is intentionally generic: no W001/P001-style hard-coded rules.
    """

    issues: list[str] = []

    person_ids = [p.id for p in dataset.people]
    customer_ids = [c.id for c in dataset.customers]
    resource_ids = [r.id for r in dataset.shared_resources]
    work_ids = [w.id for w in dataset.work_items]
    option_ids = [o.option_id for o in dataset.commercial_options]

    for entity, ids in (
        ("person", person_ids),
        ("customer", customer_ids),
        ("shared_resource", resource_ids),
        ("work_item", work_ids),
        ("commercial_option", option_ids),
    ):
        for dup in _duplicates(ids):
            issues.append(f"Duplicate {entity} id: {dup}")

    customer_set = set(customer_ids)
    resource_set = set(resource_ids)
    work_set = set(work_ids)
    option_set = set(option_ids)

    if dataset.metadata.planning_end < dataset.metadata.planning_start:
        issues.append("metadata.planning_end is before planning_start")

    for person in dataset.people:
        for unavailable in person.unavailable_ranges:
            if unavailable.end < unavailable.start:
                issues.append(
                    f"{person.id}: unavailable range ends before it starts "
                    f"({unavailable.start}..{unavailable.end})"
                )

    for work in dataset.work_items:
        if work.customer_id is not None and work.customer_id not in customer_set:
            issues.append(f"{work.id}: unknown customer_id {work.customer_id}")
        if work.due_date < work.earliest_start:
            issues.append(f"{work.id}: due_date is before earliest_start")
        for dep in work.dependencies:
            if dep not in work_set:
                issues.append(f"{work.id}: unknown dependency {dep}")
            if dep == work.id:
                issues.append(f"{work.id}: work item depends on itself")
        for conflict in work.conflicts:
            if conflict not in work_set:
                issues.append(f"{work.id}: unknown conflict {conflict}")
        for req in work.resource_requirements:
            if req.resource_id not in resource_set:
                issues.append(f"{work.id}: unknown shared resource {req.resource_id}")

    for option in dataset.commercial_options:
        if option.work_item_id not in work_set:
            issues.append(
                f"{option.option_id}: unknown work_item_id {option.work_item_id}"
            )
        for dep in option.dependencies:
            if dep not in work_set:
                issues.append(f"{option.option_id}: unknown dependency {dep}")

    valid_effect_targets = work_set | option_set | {"company_cash"}
    for effect in dataset.portfolio_effects:
        if effect.trigger not in work_set:
            issues.append(f"{effect.id}: unknown trigger {effect.trigger}")
        for target in effect.targets:
            if target not in valid_effect_targets:
                issues.append(f"{effect.id}: unknown target {target}")

    return issues
