"""Dependency, mandatory, capacity, resource, and malformed-input edges."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.decision_engine.cash_flow import CashFlowSimulator
from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.final_validation import (
    ExplanationCode,
    FinalValidationEngine,
    OperationalStatus,
    OverallStatus,
)
from app.decision_engine.final_validation.validators import validate_dependency_ordering
from app.decision_engine.planner import (
    AllocationType,
    DecisionType,
    PlanDecision,
    PlanResult,
    PlannerEngine,
    PlanStatus,
    PrerequisiteResolver,
    ResourceScheduleEntry,
    ScheduleEntry,
)
from app.domain.models import (
    CandidateDataset,
    CommercialOption,
    DateRange,
    Person,
    ResourceRequirement,
    SkillRequirement,
    WorkItem,
)
from app.services.dataset_loader import validate_references

from .factories import (
    PLAN_END,
    PLAN_START,
    make_dataset,
    make_effect,
    make_option,
    make_person,
    make_resource,
    make_work_item,
)


def test_dependency_chain_fan_in_and_fan_out_are_resolved_generically():
    works = [
        make_work_item("ROOT_NODE"),
        make_work_item("LEFT_BRANCH", dependencies=["ROOT_NODE"]),
        make_work_item("RIGHT_BRANCH", dependencies=["ROOT_NODE"]),
        make_work_item("MERGED_TARGET", dependencies=["LEFT_BRANCH", "RIGHT_BRANCH"]),
    ]
    resolver = PrerequisiteResolver(make_dataset(work_items=works))
    closure = resolver.resolve("MERGED_TARGET")
    assert closure.cycle_detected is False
    assert closure.completion_order[-1] in {"LEFT_BRANCH", "RIGHT_BRANCH"}
    assert set(closure.required_prerequisites) == {"ROOT_NODE", "LEFT_BRANCH", "RIGHT_BRANCH"}


def test_dependency_cycle_fails_cleanly_and_deterministically():
    dataset = make_dataset(work_items=[
        make_work_item("CYCLE_ALPHA", dependencies=["CYCLE_BETA"]),
        make_work_item("CYCLE_BETA", dependencies=["CYCLE_ALPHA"]),
    ])
    first = PrerequisiteResolver(dataset).resolve("CYCLE_ALPHA")
    second = PrerequisiteResolver(dataset).resolve("CYCLE_ALPHA")
    assert first == second
    assert first.cycle_detected and first.cycle_path[0] == first.cycle_path[-1]
    plan = PlannerEngine().plan(dataset)
    assert plan.selected_actions == []


def test_prerequisite_completed_before_horizon_is_not_rescheduled():
    dataset = make_dataset(work_items=[
        make_work_item("ALREADY_DONE"),
        make_work_item("NEW_DEPENDENT", dependencies=["ALREADY_DONE"]),
    ])
    plan = PlannerEngine().plan(dataset, completed_work_item_ids=frozenset({"ALREADY_DONE"}))
    assert "NEW_DEPENDENT" in plan.selected_actions
    assert all(entry.action_id != "ALREADY_DONE" for entry in plan.schedule)


def test_prerequisite_scheduled_during_horizon_finishes_first():
    dataset = make_dataset(work_items=[
        make_work_item("LIVE_PREREQUISITE", hours=2),
        make_work_item("LIVE_DEPENDENT", hours=2, dependencies=["LIVE_PREREQUISITE"]),
    ])
    plan = PlannerEngine().plan(dataset)
    prerequisite_end = max(e.date for e in plan.schedule if e.action_id == "LIVE_PREREQUISITE")
    dependent_start = min(e.date for e in plan.schedule if e.action_id == "LIVE_DEPENDENT")
    assert prerequisite_end < dependent_start


def test_selected_dependent_without_schedule_is_explicit_error():
    dataset = make_dataset(work_items=[
        make_work_item("PRE_NODE"),
        make_work_item("DEP_NODE", dependencies=["PRE_NODE"]),
    ])
    decisions = [
        PlanDecision(work_item_id="PRE_NODE", action_id="PRE_NODE", decision=DecisionType.DO),
        PlanDecision(work_item_id="DEP_NODE", action_id="DEP_NODE", decision=DecisionType.DO),
    ]
    plan = PlanResult(
        status=PlanStatus.FEASIBLE,
        decisions=decisions,
        selected_actions=["PRE_NODE", "DEP_NODE"],
        schedule=[ScheduleEntry(
            date=PLAN_START,
            action_id="PRE_NODE",
            person_id="EMP_ALPHA",
            hours=1,
            allocation_type=AllocationType.WORK,
        )],
    )
    findings = validate_dependency_ordering(dataset, plan)
    assert any(f.code == ExplanationCode.SELECTED_ACTION_SCHEDULE_MISSING for f in findings)


def test_dependency_order_violation_uses_schedule_not_details():
    dataset = make_dataset(work_items=[
        make_work_item("PRE_NODE"),
        make_work_item("DEP_NODE", dependencies=["PRE_NODE"]),
    ])
    decisions = [
        PlanDecision(
            work_item_id="PRE_NODE",
            action_id="PRE_NODE",
            decision=DecisionType.DO,
            details={"completion_date": PLAN_START},
        ),
        PlanDecision(
            work_item_id="DEP_NODE",
            action_id="DEP_NODE",
            decision=DecisionType.DO,
            details={"start_date": PLAN_START + timedelta(days=3)},
        ),
    ]
    schedule = [
        ScheduleEntry(
            date=PLAN_START + timedelta(days=1), action_id=action_id,
            person_id="EMP_ALPHA", hours=1, allocation_type=AllocationType.WORK,
        )
        for action_id in ("PRE_NODE", "DEP_NODE")
    ]
    plan = PlanResult(
        status=PlanStatus.FEASIBLE,
        decisions=decisions,
        selected_actions=["PRE_NODE", "DEP_NODE"],
        schedule=schedule,
    )
    findings = validate_dependency_ordering(dataset, plan)
    assert any(f.code == ExplanationCode.DEPENDENCY_ORDER_VIOLATION for f in findings)


@pytest.mark.parametrize(
    ("capacity", "hours", "expected"),
    [(5, 5, FeasibilityStatus.FEASIBLE), (5, 6, FeasibilityStatus.INFEASIBLE), (0, 1, FeasibilityStatus.INFEASIBLE), (2.5, 2.5, FeasibilityStatus.FEASIBLE)],
)
def test_capacity_boundaries(capacity: float, hours: float, expected: FeasibilityStatus):
    dataset = make_dataset(
        people=[make_person("CAPACITY_PERSON", capacity=capacity)],
        work_items=[make_work_item("CAPACITY_TASK", hours=hours)],
    )
    assert FeasibilityEngine().check_all(dataset)[0].status == expected


def test_uneven_capacities_use_total_team_hours_without_eight_hour_assumption():
    people = [make_person("SMALL", capacity=0.25), make_person("LARGE", capacity=3.75)]
    dataset = make_dataset(people=people, work_items=[make_work_item("FRACTIONAL_TASK", hours=4)])
    result = FeasibilityEngine().check_all(dataset)[0]
    assert result.capacity.total_team_capacity_hours == 4
    assert result.status == FeasibilityStatus.FEASIBLE


def test_entire_horizon_unavailable_and_overlapping_ranges_are_safe():
    unavailable = [
        DateRange(start=PLAN_START, end=PLAN_END),
        DateRange(start=PLAN_START + timedelta(days=1), end=PLAN_END),
    ]
    person = make_person("UNAVAILABLE_PERSON", capacity=100, unavailable=unavailable)
    mandatory = make_work_item("UNSCHEDULABLE_MANDATORY", hours=1, mandatory=True)
    plan = PlannerEngine().plan(make_dataset(people=[person], work_items=[mandatory]))
    assert plan.status == PlanStatus.INFEASIBLE
    assert plan.mandatory_infeasible == ["UNSCHEDULABLE_MANDATORY"]
    assert plan.schedule == []


def test_unavailable_range_endpoints_are_inclusive():
    blocked_day = PLAN_START + timedelta(days=2)
    person = make_person(
        "ENDPOINT_PERSON",
        capacity=6,
        unavailable=[DateRange(start=PLAN_START, end=blocked_day)],
    )
    plan = PlannerEngine().plan(make_dataset(
        people=[person],
        work_items=[make_work_item("ENDPOINT_TASK", hours=1)],
    ))
    assert all(entry.date > blocked_day for entry in plan.schedule)


def test_mandatory_is_not_auto_feasible_for_skills_capacity_or_resource():
    impossible_items = [
        make_work_item("MANDATORY_SKILL", mandatory=True, skills=[SkillRequirement(skill="quantum_simulation", min_level=9)]),
        make_work_item("MANDATORY_CAPACITY", mandatory=True, hours=11),
        make_work_item(
            "MANDATORY_RESOURCE", mandatory=True,
            resources=[ResourceRequirement(resource_id="TINY_RESOURCE", hours=2)],
        ),
    ]
    dataset = make_dataset(
        people=[make_person("LIMITED_PERSON", capacity=10)],
        resources=[make_resource("TINY_RESOURCE", capacity=1)],
        work_items=impossible_items,
    )
    feasibility = {r.work_item_id: r for r in FeasibilityEngine().check_all(dataset)}
    assert all(result.status == FeasibilityStatus.INFEASIBLE for result in feasibility.values())
    plan = PlannerEngine().plan(dataset)
    assert set(plan.mandatory_infeasible) == {item.id for item in impossible_items}


def test_mandatory_with_prerequisite_is_scheduled_as_closure():
    dataset = make_dataset(work_items=[
        make_work_item("MANDATORY_PRE"),
        make_work_item("MANDATORY_TARGET", mandatory=True, dependencies=["MANDATORY_PRE"]),
    ])
    plan = PlannerEngine().plan(dataset)
    assert plan.get_decision("MANDATORY_PRE").decision == DecisionType.ENABLING_PREREQUISITE
    assert plan.get_decision("MANDATORY_TARGET").decision == DecisionType.DO


def test_silently_omitted_mandatory_is_operationally_infeasible():
    dataset = make_dataset(work_items=[make_work_item("OMITTED_MANDATORY", mandatory=True)])
    malformed_plan = PlanResult(status=PlanStatus.FEASIBLE)
    cash = CashFlowSimulator().simulate(dataset, malformed_plan)
    result = FinalValidationEngine().validate(dataset, malformed_plan, cash)
    assert result.operational_status == OperationalStatus.OPERATIONALLY_INFEASIBLE
    assert result.overall_status == OverallStatus.PLAN_INFEASIBLE
    assert any(f.code == ExplanationCode.MANDATORY_WORK_OMITTED for f in result.critical_issues)


def test_resource_exact_capacity_and_arbitrary_many_resources():
    resources = [make_resource(f"DEVICE_{index}", capacity=1) for index in range(3)]
    requirements = [ResourceRequirement(resource_id=r.id, hours=1) for r in resources]
    task = make_work_item("MULTI_DEVICE_TASK", resources=requirements)
    dataset = make_dataset(resources=resources, work_items=[task])
    result = FeasibilityEngine().check_all(dataset)[0]
    plan = PlannerEngine().plan(dataset)
    assert result.status == FeasibilityStatus.FEASIBLE
    assert {usage.resource_id for usage in plan.resource_capacity} == {r.id for r in resources}


def test_two_independent_resources_can_be_used_on_same_day():
    resources = [
        make_resource("DEVICE_LEFT", capacity=1, exclusive=True),
        make_resource("DEVICE_RIGHT", capacity=1, exclusive=True),
    ]
    tasks = [
        make_work_item("LEFT_TASK", resources=[ResourceRequirement(resource_id="DEVICE_LEFT", hours=1)]),
        make_work_item("RIGHT_TASK", resources=[ResourceRequirement(resource_id="DEVICE_RIGHT", hours=1)]),
    ]
    plan = PlannerEngine().plan(make_dataset(
        people=[make_person("ONE_DAY_TEAM", capacity=2)],
        resources=resources,
        work_items=tasks,
        start=PLAN_START,
        end=PLAN_START,
    ))
    assert set(plan.selected_actions) == {"LEFT_TASK", "RIGHT_TASK"}


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_work",
        "missing_customer",
        "missing_dependency",
        "missing_resource",
        "orphan_option",
        "missing_effect_trigger",
        "missing_effect_target",
    ],
)
def test_invalid_references_are_rejected_cleanly(mutation: str):
    customer_id = "KNOWN_CUSTOMER"
    resource_id = "KNOWN_RESOURCE"
    work = make_work_item("KNOWN_WORK", customer_id=customer_id)
    dataset = make_dataset(
        customers=[],
        resources=[make_resource(resource_id)],
        work_items=[work],
    )
    if mutation == "duplicate_work":
        dataset = dataset.model_copy(update={"work_items": [work, work]})
    elif mutation == "missing_customer":
        pass
    elif mutation == "missing_dependency":
        dataset = dataset.model_copy(update={"work_items": [work.model_copy(update={"customer_id": None, "dependencies": ["GHOST"]})]})
    elif mutation == "missing_resource":
        dataset = dataset.model_copy(update={"work_items": [work.model_copy(update={"customer_id": None, "resource_requirements": [ResourceRequirement(resource_id="GHOST", hours=1)]})]})
    elif mutation == "orphan_option":
        dataset = dataset.model_copy(update={"work_items": [work.model_copy(update={"customer_id": None})], "commercial_options": [make_option("GHOST_PARENT", "ORPHAN_OFFER")]})
    elif mutation == "missing_effect_trigger":
        dataset = dataset.model_copy(update={"work_items": [work.model_copy(update={"customer_id": None})], "portfolio_effects": [make_effect("BAD_EFFECT", trigger="GHOST", targets=["KNOWN_WORK"], effect_type="quality_prerequisite")]})
    elif mutation == "missing_effect_target":
        dataset = dataset.model_copy(update={"work_items": [work.model_copy(update={"customer_id": None})], "portfolio_effects": [make_effect("BAD_EFFECT", trigger="KNOWN_WORK", targets=["GHOST"], effect_type="quality_prerequisite")]})
    assert validate_references(dataset), mutation


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (WorkItem, "required_hours", -1),
        (CommercialOption, "estimated_win_probability", 1.01),
        (Person, "capacity_hours", -0.1),
    ],
)
def test_domain_constraints_reject_invalid_numbers(model, field: str, value):
    if model is WorkItem:
        payload = make_work_item().model_dump()
    elif model is CommercialOption:
        payload = make_option().model_dump()
    else:
        payload = make_person().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_invalid_date_string_is_rejected():
    payload = make_work_item().model_dump()
    payload["earliest_start"] = "not-a-date"
    with pytest.raises(ValidationError):
        WorkItem.model_validate(payload)


def test_due_before_earliest_is_semantic_validation_error():
    work = make_work_item("TIME_TRAVEL", earliest=PLAN_END, due=PLAN_START)
    assert any("due_date is before earliest_start" in issue for issue in validate_references(make_dataset(work_items=[work])))
