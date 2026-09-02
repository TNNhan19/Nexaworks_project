from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS
from app.services.baseline_summary import summary_as_dict
from app.services.dataset_loader import load_dataset

from .comparison import compare_runs
from .errors import RunNotFoundError, ScenarioNotFoundError, ScenarioValidationError
from .models import RunComparison, Scenario, ScenarioCreate, ScenarioPatch, ScenarioRun
from .overrides import apply_overrides
from .pipeline import DecisionPipelineService
from .repository import SQLiteScenarioRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScenarioService:
    def __init__(self, repository: SQLiteScenarioRepository, dataset_path: str | Path,
                 schema_path: str | Path, pipeline: DecisionPipelineService | None = None):
        self.repository = repository
        self.dataset_path = Path(dataset_path)
        self.schema_path = Path(schema_path)
        self.pipeline = pipeline or DecisionPipelineService()

    def _baseline(self):
        return load_dataset(self.dataset_path, self.schema_path)

    def baseline_summary(self) -> dict:
        dataset = self._baseline()
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

    @staticmethod
    def _validate_manual_constraints(dataset, overrides) -> None:
        work = {item.id: item for item in dataset.work_items}
        unknown = sorted(set(overrides.deferred_work_item_ids) - set(work))
        mandatory = sorted(
            work_id for work_id in overrides.deferred_work_item_ids
            if work_id in work and work[work_id].mandatory
        )
        errors = []
        if unknown:
            errors.append(f"unknown deferred work item IDs: {unknown}")
        if mandatory:
            errors.append(f"mandatory work cannot be manually deferred: {mandatory}")
        if errors:
            raise ScenarioValidationError("Scenario manual constraints are invalid", errors)

    def create(self, request: ScenarioCreate) -> Scenario:
        effective = apply_overrides(self._baseline(), request.overrides)
        self._validate_manual_constraints(effective, request.overrides)
        timestamp = _now()
        scenario = Scenario(
            id=str(uuid4()),
            name=request.name,
            description=request.description,
            overrides=request.overrides,
            status=request.status,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.repository.save_scenario(scenario)
        return scenario

    def list(self) -> list[Scenario]:
        return self.repository.list_scenarios()

    def get(self, scenario_id: str) -> Scenario:
        scenario = self.repository.get_scenario(scenario_id)
        if scenario is None:
            raise ScenarioNotFoundError(f"Scenario not found: {scenario_id}")
        return scenario

    def update(self, scenario_id: str, request: ScenarioPatch) -> Scenario:
        current = self.get(scenario_id)
        changes = {
            field: getattr(request, field)
            for field in request.model_fields_set
        }
        candidate = Scenario.model_validate(
            current.model_copy(update={**changes, "updated_at": _now()}).model_dump()
        )
        effective = apply_overrides(self._baseline(), candidate.overrides)
        self._validate_manual_constraints(effective, candidate.overrides)
        self.repository.save_scenario(candidate)
        return candidate

    def delete(self, scenario_id: str) -> None:
        self.get(scenario_id)
        self.repository.delete_scenario(scenario_id)

    def effective_dataset(self, scenario_id: str):
        scenario = self.get(scenario_id)
        return apply_overrides(self._baseline(), scenario.overrides)

    def run(self, scenario_id: str) -> ScenarioRun:
        scenario = self.get(scenario_id)
        effective = apply_overrides(self._baseline(), scenario.overrides)
        common = {
            "run_id": str(uuid4()),
            "scenario_id": scenario_id,
            "timestamp": _now(),
            "effective_input": effective.model_dump(mode="json"),
            "assumptions": {
                "version": "V1",
                "values": DEFAULT_ASSUMPTIONS.model_dump(mode="json"),
            },
        }
        try:
            outputs = self.pipeline.run(
                effective,
                deferred_work_item_ids=frozenset(scenario.overrides.deferred_work_item_ids),
            )
        except Exception as exc:
            failed = ScenarioRun(**common, status="FAILED",
                error={"code": "PIPELINE_EXECUTION_FAILED", "message": str(exc)})
            self.repository.save_run(failed)
            raise
        completed = ScenarioRun(**common, **outputs, status="COMPLETED")
        self.repository.save_run(completed)
        return completed

    def list_runs(self, scenario_id: str) -> list[ScenarioRun]:
        self.get(scenario_id)
        return self.repository.list_runs(scenario_id)

    def get_run(self, run_id: str) -> ScenarioRun:
        run = self.repository.get_run(run_id)
        if run is None:
            raise RunNotFoundError(f"Run not found: {run_id}")
        return run

    def compare(self, run_a_id: str, run_b_id: str) -> RunComparison:
        return compare_runs(self.get_run(run_a_id), self.get_run(run_b_id))
