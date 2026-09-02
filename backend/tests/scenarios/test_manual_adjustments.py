from app.scenarios.errors import ScenarioValidationError
from app.scenarios.models import ScenarioCreate, ScenarioOverrides
from tests.scenarios.fixtures import scenario_service


def _decision(plan: dict, action_id: str) -> dict:
    return next(item for item in plan["decisions"] if item["action_id"] == action_id)


def test_optional_work_can_be_deferred_without_mutating_baseline(scenario_service):
    service = scenario_service
    baseline = service.pipeline.run(service._baseline())
    assert _decision(baseline["plan"], "W023")["decision"] == "DO"

    scenario = service.create(ScenarioCreate(
        name="Defer low-priority spend",
        overrides=ScenarioOverrides(deferred_work_item_ids=["W023"]),
    ))
    result = service.run(scenario.id)

    decision = _decision(result.plan, "W023")
    assert decision["decision"] == "DELAY"
    assert "USER_DEFERRED" in decision["reason_codes"]
    rerun_baseline = service.pipeline.run(service._baseline())
    assert _decision(rerun_baseline["plan"], "W023")["decision"] == "DO"


def test_unknown_or_mandatory_work_cannot_be_manually_deferred(scenario_service):
    service = scenario_service
    for work_id in ("UNKNOWN-WORK", "W001"):
        try:
            service.create(ScenarioCreate(
                name=f"Invalid {work_id}",
                overrides=ScenarioOverrides(deferred_work_item_ids=[work_id]),
            ))
        except ScenarioValidationError:
            pass
        else:
            raise AssertionError(f"Expected {work_id} to be rejected")
