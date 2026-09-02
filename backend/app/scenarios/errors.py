from __future__ import annotations


class ScenarioError(Exception):
    code = "SCENARIO_ERROR"

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class ScenarioValidationError(ScenarioError):
    code = "INVALID_SCENARIO"


class ScenarioNotFoundError(ScenarioError):
    code = "SCENARIO_NOT_FOUND"


class RunNotFoundError(ScenarioError):
    code = "RUN_NOT_FOUND"


class InvalidRunStateError(ScenarioError):
    code = "INVALID_RUN_STATE"
