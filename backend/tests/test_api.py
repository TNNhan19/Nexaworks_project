from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dataset_summary_endpoint() -> None:
    response = client.get("/api/v1/dataset/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["people_count"] == 7
    assert body["work_item_count"] == 24
    assert body["total_people_capacity_hours"] == 748.0
