from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.dataset_loader import read_json


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "candidate_dataset.json"
client = TestClient(app)


def test_sample_catalog_exposes_dynamic_work_facts_without_running_plan() -> None:
    raw = read_json(DATASET_PATH)
    response = client.get("/api/v1/planning/sample")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["work_item_count"] == len(raw["work_items"])
    assert body["summary"]["people_count"] == len(raw["people"])
    assert len(body["work_items"]) == len(raw["work_items"])
    assert {"id", "title", "type", "mandatory", "required_hours", "due_date"} <= set(
        body["work_items"][0]
    )
    assert "plan" not in body
    assert "final_decision" not in body


def test_review_accepts_supported_canonical_json_without_mutating_it() -> None:
    raw = read_json(DATASET_PATH)
    response = client.post("/api/v1/planning/review", json={"dataset": raw})
    assert response.status_code == 200
    assert response.json()["summary"]["dataset_id"] == raw["metadata"]["dataset_id"]
    assert read_json(DATASET_PATH) == raw


def test_analyze_stops_before_planning_and_schedule_generation() -> None:
    response = client.post("/api/v1/planning/analyze", json={})
    assert response.status_code == 200
    body = response.json()
    assert {"feasibility", "portfolio", "commercial", "scoring"} <= set(body)
    assert "plan" not in body
    assert "cash_flow" not in body
    assert "final_decision" not in body


def test_generate_matches_existing_canonical_planner_results() -> None:
    generated = client.post("/api/v1/planning/generate", json={})
    existing = client.get("/api/v1/plan")
    assert generated.status_code == 200
    assert existing.status_code == 200
    generated_plan = generated.json()["plan"]
    existing_plan = existing.json()
    assert generated_plan["status"] == existing_plan["status"]
    assert generated_plan["selected_actions"] == existing_plan["selected_actions"]
    assert generated_plan["delayed_actions"] == existing_plan["delayed_actions"]
    assert generated_plan["no_bid_opportunities"] == existing_plan["no_bid_opportunities"]
    assert generated_plan["schedule"] == existing_plan["schedule"]


def test_invalid_uploaded_dataset_returns_structured_validation_error() -> None:
    response = client.post(
        "/api/v1/planning/review",
        json={"dataset": {"metadata": {"dataset_id": "UNSEEN-DATASET"}}},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "PLANNING_DATA_INVALID"
    assert detail["errors"]
