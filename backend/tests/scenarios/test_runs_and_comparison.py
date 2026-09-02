from __future__ import annotations

from pathlib import Path

import pytest

from app.api.scenarios import DATASET_PATH, SCHEMA_PATH
from app.scenarios.models import ScenarioCreate, ScenarioPatch
from app.scenarios.repository import SQLiteScenarioRepository
from app.scenarios.service import ScenarioService
from tests.scenarios.fixtures import scenario_client, scenario_service


@pytest.fixture(scope="module")
def run_bundle(tmp_path_factory):
    db = tmp_path_factory.mktemp("scenario-runs") / "runs.sqlite3"
    service = ScenarioService(SQLiteScenarioRepository(db), DATASET_PATH, SCHEMA_PATH)
    baseline = service.create(ScenarioCreate(name="baseline-like"))
    modified = service.create(ScenarioCreate.model_validate({
        "name": "cash 18m",
        "overrides": {"company": {"starting_cash_jpy": 18_000_000}},
    }))
    run_a1 = service.run(baseline.id)
    run_b = service.run(modified.id)
    run_a2 = service.run(baseline.id)
    return service, db, baseline, modified, run_a1, run_b, run_a2


def _business_payload(run):
    return {
        "feasibility": run.feasibility,
        "portfolio": run.portfolio,
        "commercial": run.commercial,
        "scoring": run.scoring,
        "plan": run.plan,
        "cash_flow": run.cash_flow,
        "final_decision": run.final_decision,
    }


def test_full_pipeline_run_contains_every_phase(run_bundle):
    run = run_bundle[4]
    assert run.status == "COMPLETED"
    assert run.feasibility and run.portfolio and run.commercial and run.scoring
    assert run.plan and run.cash_flow and run.final_decision


def test_run_history_and_direct_retrieval_are_persisted(run_bundle):
    service, _, baseline, _, run_a1, _, run_a2 = run_bundle
    history = service.list_runs(baseline.id)
    assert [item.run_id for item in history] == [run_a1.run_id, run_a2.run_id]
    assert service.get_run(run_a1.run_id) == run_a1


def test_persistence_survives_service_reinstantiation(run_bundle):
    _, db, baseline, _, run_a1, _, _ = run_bundle
    restored = ScenarioService(SQLiteScenarioRepository(db), DATASET_PATH, SCHEMA_PATH)
    assert restored.get(baseline.id) == baseline
    assert restored.get_run(run_a1.run_id) == run_a1


def test_a_b_a_isolation_and_repeat_determinism(run_bundle):
    _, _, _, _, run_a1, run_b, run_a2 = run_bundle
    assert _business_payload(run_a1) == _business_payload(run_a2)
    assert run_a1.effective_input["company"]["starting_cash_jpy"] != 18_000_000
    assert run_b.effective_input["company"]["starting_cash_jpy"] == 18_000_000


def test_old_run_snapshot_unchanged_after_scenario_edit(run_bundle):
    service, _, baseline, _, run_a1, _, _ = run_bundle
    before = run_a1.model_dump(mode="json")
    service.update(baseline.id, ScenarioPatch(description="edited later"))
    assert service.get_run(run_a1.run_id).model_dump(mode="json") == before


def test_structured_run_comparison_has_status_cash_and_business_deltas(run_bundle):
    service, _, _, _, run_a1, run_b, _ = run_bundle
    comparison = service.compare(run_a1.run_id, run_b.run_id)
    assert set(comparison.status_transition) == {
        "overall_status", "operational_status", "financial_status",
    }
    assert comparison.cash["expected_ending_cash_jpy"]["delta"] == (
        run_b.cash_flow["scenarios"]["EXPECTED"]["ending_cash_jpy"]
        - run_a1.cash_flow["scenarios"]["EXPECTED"]["ending_cash_jpy"]
    )
    assert set(comparison.selected) == {"added", "removed"}
    assert not hasattr(comparison, "better")


def test_run_api_history_get_compare_and_missing(scenario_client):
    created = scenario_client.post("/api/v1/scenarios", json={"name": "api run"}).json()
    run_response = scenario_client.post(f"/api/v1/scenarios/{created['id']}/run")
    assert run_response.status_code == 201
    run_id = run_response.json()["run_id"]
    assert scenario_client.get(f"/api/v1/runs/{run_id}").status_code == 200
    assert len(scenario_client.get(f"/api/v1/scenarios/{created['id']}/runs").json()) == 1
    compared = scenario_client.get(
        "/api/v1/runs/compare", params={"run_a_id": run_id, "run_b_id": run_id}
    )
    assert compared.status_code == 200
    missing = scenario_client.get("/api/v1/runs/not-found")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "RUN_NOT_FOUND"


def test_delete_scenario_does_not_delete_historical_run(run_bundle):
    service, _, _, _, _, run_b, _ = run_bundle
    scenario_id = run_b.scenario_id
    service.delete(scenario_id)
    assert service.get_run(run_b.run_id) == run_b
