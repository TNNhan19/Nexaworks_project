from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_get_workforce_people_returns_all_people():
    client = TestClient(app)
    response = client.get("/api/v1/workforce/people")
    assert response.status_code == 200
    people = response.json()
    assert isinstance(people, list)
    assert len(people) > 0

    first = people[0]
    assert "id" in first
    assert "person_id" in first
    assert "name" in first
    assert "capacity_hours" in first
    assert "skills" in first
    assert isinstance(first["skills"], dict)
    assert "languages" in first
    assert isinstance(first["languages"], list)
    assert "unavailable_ranges" in first
    assert isinstance(first["unavailable_ranges"], list)
