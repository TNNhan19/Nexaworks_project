from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import Scenario, ScenarioRun


class SQLiteScenarioRepository:
    """Small SQLite repository with immutable run payloads."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _session(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._session() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS scenarios (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenario_runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_scenario_time
                    ON scenario_runs(scenario_id, timestamp, run_id);
                """
            )

    def save_scenario(self, scenario: Scenario) -> None:
        serializable = scenario.model_dump(mode="json")
        # Preserve which nullable override fields were explicitly supplied.
        serializable["overrides"] = scenario.overrides.model_dump(
            mode="json", exclude_unset=True
        )
        payload = json.dumps(serializable, separators=(",", ":"))
        with self._session() as connection:
            connection.execute(
                """INSERT INTO scenarios(id, created_at, updated_at, payload)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       updated_at=excluded.updated_at, payload=excluded.payload""",
                (scenario.id, scenario.created_at.isoformat(), scenario.updated_at.isoformat(), payload),
            )

    def get_scenario(self, scenario_id: str) -> Scenario | None:
        with self._session() as connection:
            row = connection.execute(
                "SELECT payload FROM scenarios WHERE id = ?", (scenario_id,)
            ).fetchone()
        return Scenario.model_validate_json(row["payload"]) if row else None

    def list_scenarios(self) -> list[Scenario]:
        with self._session() as connection:
            rows = connection.execute(
                "SELECT payload FROM scenarios ORDER BY created_at, id"
            ).fetchall()
        return [Scenario.model_validate_json(row["payload"]) for row in rows]

    def delete_scenario(self, scenario_id: str) -> bool:
        with self._session() as connection:
            cursor = connection.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        return cursor.rowcount > 0

    def save_run(self, run: ScenarioRun) -> None:
        with self._session() as connection:
            connection.execute(
                "INSERT INTO scenario_runs(run_id, scenario_id, timestamp, payload) VALUES (?, ?, ?, ?)",
                (run.run_id, run.scenario_id, run.timestamp.isoformat(), run.model_dump_json()),
            )

    def get_run(self, run_id: str) -> ScenarioRun | None:
        with self._session() as connection:
            row = connection.execute(
                "SELECT payload FROM scenario_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return ScenarioRun.model_validate_json(row["payload"]) if row else None

    def list_runs(self, scenario_id: str) -> list[ScenarioRun]:
        with self._session() as connection:
            rows = connection.execute(
                "SELECT payload FROM scenario_runs WHERE scenario_id = ? ORDER BY timestamp, run_id",
                (scenario_id,),
            ).fetchall()
        return [ScenarioRun.model_validate_json(row["payload"]) for row in rows]
