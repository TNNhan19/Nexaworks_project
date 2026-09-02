from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.scenarios import DATASET_PATH, SCHEMA_PATH, get_scenario_service
from app.main import app
from app.scenarios.repository import SQLiteScenarioRepository
from app.scenarios.service import ScenarioService


@pytest.fixture
def scenario_service(tmp_path: Path) -> ScenarioService:
    return ScenarioService(
        SQLiteScenarioRepository(tmp_path / "scenarios.sqlite3"),
        DATASET_PATH,
        SCHEMA_PATH,
    )


@pytest.fixture
def scenario_client(scenario_service: ScenarioService):
    app.dependency_overrides[get_scenario_service] = lambda: scenario_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
