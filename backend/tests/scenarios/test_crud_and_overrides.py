from __future__ import annotations

from app.scenarios.models import ScenarioCreate
from tests.scenarios.fixtures import scenario_client, scenario_service


def test_scenario_crud_and_structured_missing_error(scenario_client):
    created = scenario_client.post("/api/v1/scenarios", json={"name": "Capacity case"})
    assert created.status_code == 201
    scenario_id = created.json()["id"]
    assert scenario_client.get("/api/v1/scenarios").json()[0]["id"] == scenario_id
    updated = scenario_client.patch(
        f"/api/v1/scenarios/{scenario_id}",
        json={"description": "updated", "status": "INACTIVE"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "updated"
    assert scenario_client.delete(f"/api/v1/scenarios/{scenario_id}").status_code == 204
    missing = scenario_client.get(f"/api/v1/scenarios/{scenario_id}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "SCENARIO_NOT_FOUND"


def test_baseline_and_health_endpoints(scenario_client):
    assert scenario_client.get("/health").json() == {"status": "ok"}
    summary = scenario_client.get("/api/v1/baseline/summary")
    assert summary.status_code == 200
    assert summary.json()["dataset_id"]
    assert summary.json()["starting_cash_jpy"] >= 0


def test_valid_overrides_do_not_mutate_baseline_or_another_scenario(scenario_service):
    baseline = scenario_service._baseline().model_dump(mode="json")
    person_id = baseline["people"][0]["id"]
    work_id = baseline["work_items"][0]["id"]
    changed = scenario_service.create(ScenarioCreate.model_validate({
        "name": "changed",
        "overrides": {
            "company": {"starting_cash_jpy": 18_000_000},
            "people": [{"person_id": person_id, "capacity_hours": 1.5}],
            "work_items": [{"work_item_id": work_id, "required_hours": 2.5}],
        },
    }))
    untouched = scenario_service.create(ScenarioCreate(name="untouched"))
    effective_changed = scenario_service.effective_dataset(changed.id)
    effective_untouched = scenario_service.effective_dataset(untouched.id)
    assert effective_changed.company.starting_cash_jpy == 18_000_000
    assert effective_changed.people[0].capacity_hours == 1.5
    assert effective_untouched.model_dump(mode="json") == baseline
    assert scenario_service._baseline().model_dump(mode="json") == baseline


def test_unknown_override_target_returns_structured_400(scenario_client):
    response = scenario_client.post("/api/v1/scenarios", json={
        "name": "bad target",
        "overrides": {"people": [{"person_id": "DOES_NOT_EXIST", "capacity_hours": 1}]},
    })
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_SCENARIO"


def test_broken_dependency_reference_returns_400(scenario_client, scenario_service):
    work_id = scenario_service._baseline().work_items[0].id
    response = scenario_client.post("/api/v1/scenarios", json={
        "name": "bad reference",
        "overrides": {"work_items": [{
            "work_item_id": work_id, "dependencies": ["MISSING_TASK"],
        }]},
    })
    assert response.status_code == 400
    assert "invalid references" in response.json()["detail"]["message"].lower()


def test_invalid_values_and_arbitrary_fields_are_rejected(scenario_client):
    negative = scenario_client.post("/api/v1/scenarios", json={
        "name": "negative",
        "overrides": {"company": {"starting_cash_jpy": -1}},
    })
    injected = scenario_client.post("/api/v1/scenarios", json={
        "name": "injected",
        "overrides": {"company": {"secret_rule": True}},
    })
    assert negative.status_code == 422
    assert injected.status_code == 422


def test_probability_and_malformed_date_are_rejected(scenario_client):
    probability = scenario_client.post("/api/v1/scenarios", json={
        "name": "probability",
        "overrides": {"commercial_options": [{
            "option_id": "ANY", "estimated_win_probability": 1.1,
        }]},
    })
    malformed = scenario_client.post("/api/v1/scenarios", json={
        "name": "date",
        "overrides": {"work_items": [{
            "work_item_id": "ANY", "due_date": "not-a-date",
        }]},
    })
    assert probability.status_code == 422
    assert malformed.status_code == 422
