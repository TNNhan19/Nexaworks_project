"""Focused Phase 2E heuristic-planner tests."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.decision_engine.planner import (
    AllocationType,
    AssignmentRole,
    DecisionType,
    PlannerEngine,
    PlannerReasonCode,
    PrerequisiteResolver,
)
from app.decision_engine.scoring import ScoringEngine
from app.decision_engine.commercial import CommercialEvaluationEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.domain.models import (
    CandidateDataset,
    CommercialOption,
    Company,
    DateRange,
    Enumerations,
    Metadata,
    Person,
    PortfolioEffect,
    ResourceRequirement,
    SharedResource,
    SkillRequirement,
    WorkItem,
)
from app.services.dataset_loader import load_dataset


def person(pid="P1", capacity=40, skills=None, languages=None, unavailable=None):
    return Person(
        id=pid, name=pid, capacity_hours=capacity,
        skills=skills or {"general": 5}, languages=languages or ["en"],
        unavailable_ranges=unavailable or [],
    )


def work(
    wid, hours=1, *, mandatory=False, deps=None, skills=None, languages=None,
    earliest=date(2026, 1, 1), due=date(2026, 1, 4), wtype="delivery",
    revenue=0, resources=None,
):
    return WorkItem(
        id=wid, title=wid, type=wtype, mandatory=mandatory,
        required_hours=hours, earliest_start=earliest, due_date=due,
        dependencies=deps or [], required_skills=skills or [],
        required_languages=languages or [], resource_requirements=resources or [],
        revenue_jpy=revenue, strategic_value=1,
    )


def option(wid, oid, *, delivery=0, price=100, probability=1, deps=None, label=None):
    return CommercialOption(
        work_item_id=wid, option_id=oid, label=label or oid,
        price_jpy=price, direct_cost_jpy=0, delivery_hours=delivery,
        payment_days=1, estimated_win_probability=probability,
        follow_on_value_jpy=0, dependencies=deps or [],
    )


def dataset(
    works, *, people=None, options=None, effects=None, resources=None,
    start=date(2026, 1, 1), end=date(2026, 1, 4),
):
    return CandidateDataset(
        metadata=Metadata(
            dataset_id="T", version="1", planning_start=start,
            planning_end=end, currency="JPY",
        ),
        company=Company(
            name="T", starting_cash_jpy=1, fixed_cash_outflow_jpy=0,
            minimum_cash_buffer_jpy=0,
        ),
        people=people or [person()], customers=[], shared_resources=resources or [],
        work_items=works, commercial_options=options or [],
        portfolio_effects=effects or [], enumerations=Enumerations(),
    )


@pytest.fixture(scope="module")
def canonical():
    root = Path(__file__).resolve().parents[2]
    return load_dataset(root / "data/candidate_dataset.json", root / "data/candidate_dataset.schema.json")


@pytest.fixture(scope="module")
def canonical_plan(canonical):
    return PlannerEngine().plan(canonical)


def test_01_mandatory_selected_before_optional():
    result = PlannerEngine().plan(dataset([
        work("M", mandatory=True), work("O", revenue=1_000_000),
    ], people=[person(capacity=2)]))
    selected = [d.action_id for d in result.decisions if d.decision == DecisionType.DO]
    assert selected[0] == "M"


def test_02_mandatory_blocked_prerequisite_closure():
    result = PlannerEngine().plan(dataset([
        work("PRE"), work("TARGET", mandatory=True, deps=["PRE"]),
    ]))
    assert result.get_decision("PRE").decision == DecisionType.ENABLING_PREREQUISITE
    assert result.get_decision("TARGET").decision == DecisionType.DO


def test_03_w005_scheduled_before_w001(canonical_plan):
    assert canonical_plan.get_decision("W005").details["completion_date"] < min(
        entry.date for entry in canonical_plan.schedule if entry.action_id == "W001"
    )


def test_04_blocked_candidate_becomes_selectable_after_completion():
    result = PlannerEngine().plan(dataset([work("A"), work("B", deps=["A"], revenue=100)]))
    assert "B" in result.selected_actions


def test_05_transitive_dependency_closure():
    data = dataset([work("C"), work("B", deps=["C"]), work("A", deps=["B"])])
    assert PrerequisiteResolver(data).resolve("A").completion_order == ["C", "B"]


def test_06_dependency_cycle_detection():
    data = dataset([work("A", deps=["B"]), work("B", deps=["A"])])
    closure = PrerequisiteResolver(data).resolve("A")
    assert closure.cycle_detected and closure.cycle_path[0] == closure.cycle_path[-1]


def unlock_dataset(trigger_hours=1, capacity=10):
    opp = work("OPP", hours=1, wtype="sales_opportunity")
    trigger = work("TRIGGER", hours=trigger_hours)
    opt = option("OPP", "OPP-A", delivery=1, deps=["TRIGGER"])
    effect = PortfolioEffect(
        id="E", trigger="TRIGGER", targets=["OPP-A"],
        effect={"type": "commercial_option_unlock"},
    )
    return dataset([trigger, opp], people=[person(capacity=capacity)], options=[opt], effects=[effect])


def test_07_trigger_completion_unlocks_option():
    result = PlannerEngine().plan(unlock_dataset())
    assert result.get_decision("OPP-A").decision == DecisionType.SELECT_OPTION


def test_08_w007b_closure_includes_w005_and_w022(canonical):
    closure = PrerequisiteResolver(canonical).resolve("W007-B")
    assert set(closure.required_prerequisites) == {"W005", "W022"}
    assert closure.unlock_triggers == ["W022"]


def test_09_locked_option_not_selected_when_trigger_cannot_fit():
    result = PlannerEngine().plan(unlock_dataset(trigger_hours=10, capacity=2))
    assert result.get_decision("OPP-A") is None
    assert "OPP" in result.no_bid_opportunities


def test_10_mutually_exclusive_commercial_options():
    opp = work("OPP", wtype="sales_opportunity")
    result = PlannerEngine().plan(dataset(
        [opp], options=[option("OPP", "A"), option("OPP", "B")],
    ))
    assert sum(d.decision == DecisionType.SELECT_OPTION for d in result.decisions) == 1


def test_11_maximum_one_option_per_opportunity():
    opp = work("OPP", wtype="sales_opportunity")
    result = PlannerEngine().plan(dataset([opp], options=[option("OPP", "A"), option("OPP", "B")]))
    assert len([a for a in result.selected_actions if a in {"A", "B"}]) == 1


def test_12_planner_level_no_bid():
    opp = work("OPP", hours=5, wtype="sales_opportunity")
    result = PlannerEngine().plan(dataset([opp], people=[person(capacity=1)], options=[option("OPP", "A")]))
    assert result.get_decision("OPP").decision == DecisionType.NO_BID


def test_13_w011c_style_zero_option_is_select_option():
    opp = work("OPP", wtype="sales_opportunity")
    result = PlannerEngine().plan(dataset([opp], options=[option("OPP", "OPP-C", price=0, delivery=0, label="No-bid")]))
    assert result.get_decision("OPP-C").decision == DecisionType.SELECT_OPTION


def test_14_zero_value_label_has_no_no_bid_inference():
    opp = work("OPP", wtype="sales_opportunity")
    result = PlannerEngine().plan(dataset([opp], options=[option("OPP", "FREE", price=0, delivery=0, label="Free pilot")]))
    assert "OPP" not in result.no_bid_opportunities and "FREE" in result.selected_actions


def test_15_full_if_committed_capacity():
    opp = work("OPP", hours=2, wtype="sales_opportunity")
    result = PlannerEngine().plan(dataset([opp], options=[option("OPP", "A", delivery=6, probability=.25)]))
    assert sum(a.assigned_hours for a in result.assignments if a.action_id == "A") == pytest.approx(8)


def test_16_expected_delivery_hours_not_committed_denominator():
    opp = work("OPP", hours=2, wtype="sales_opportunity")
    result = PlannerEngine().plan(dataset([opp], options=[option("OPP", "A", delivery=6, probability=.25)]))
    reserved = sum(e.hours for e in result.schedule if e.action_id == "A" and e.allocation_type == AllocationType.RESERVED_DELIVERY)
    assert reserved == pytest.approx(6)


def test_17_skill_team_coverage():
    people = [person("AI", skills={"ai": 5}), person("PM", skills={"pm": 5})]
    item = work("W", hours=4, skills=[SkillRequirement(skill="ai", min_level=4), SkillRequirement(skill="pm", min_level=4)])
    result = PlannerEngine().plan(dataset([item], people=people))
    assert "W" in result.selected_actions


def test_18_skill_levels_are_not_summed():
    people = [person("A", skills={"ai": 3}), person("B", skills={"ai": 3})]
    item = work("W", skills=[SkillRequirement(skill="ai", min_level=4)])
    assert "W" not in PlannerEngine().plan(dataset([item], people=people)).selected_actions


def test_19_skill_witness_has_positive_allocation():
    item = work("W", skills=[SkillRequirement(skill="general", min_level=5)])
    result = PlannerEngine().plan(dataset([item]))
    witness = next(a for a in result.assignments if a.action_id == "W" and a.skills_covered)
    assert witness.assigned_hours > 0


def test_20_language_coverage():
    item = work("W", languages=["ja"])
    result = PlannerEngine().plan(dataset([item], people=[person(languages=["en"])]))
    assert "W" not in result.selected_actions


def test_skill_policy_applies_to_every_assignee_and_owner(canonical, canonical_plan):
    work_map = {item.id: item for item in canonical.work_items}
    decision_work = {
        decision.action_id: work_map[decision.work_item_id]
        for decision in canonical_plan.decisions
        if decision.decision in {
            DecisionType.DO,
            DecisionType.ENABLING_PREREQUISITE,
            DecisionType.SELECT_OPTION,
        }
    }
    people = {person.id: person for person in canonical.people}

    for assignment in canonical_plan.assignments:
        item = decision_work[assignment.action_id]
        person_item = people[assignment.person_id]
        if item.required_skills:
            assert any(
                person_item.skills.get(req.skill, 0) >= req.min_level
                for req in item.required_skills
            )

    for action_id, item in decision_work.items():
        owners = [
            assignment for assignment in canonical_plan.assignments
            if assignment.action_id == action_id
            and assignment.assignment_role == AssignmentRole.OWNER
        ]
        assert len(owners) == 1
        owner = people[owners[0].person_id]
        assert all(language in owner.languages for language in item.required_languages)
        if item.required_skills:
            assert any(
                owner.skills.get(req.skill, 0) >= req.min_level
                for req in item.required_skills
            )


def test_w021_collection_is_owned_by_qualified_business_person(canonical, canonical_plan):
    people = {person.id: person for person in canonical.people}
    item = next(work_item for work_item in canonical.work_items if work_item.id == "W021")
    assignments = [
        assignment for assignment in canonical_plan.assignments
        if assignment.action_id == "W021"
    ]

    assert assignments
    assert all(
        any(
            people[assignment.person_id].skills.get(req.skill, 0) >= req.min_level
            for req in item.required_skills
        )
        for assignment in assignments
    )
    owner = next(
        assignment for assignment in assignments
        if assignment.assignment_role == AssignmentRole.OWNER
    )
    assert all(language in people[owner.person_id].languages for language in item.required_languages)
    assert set(owner.skills_covered) == {"sales", "project_management"}


def test_insufficient_qualified_capacity_maps_to_business_decision():
    qualified = person("Q", capacity=2, skills={"robotics": 5})
    unqualified = person("U", capacity=100, skills={"general": 5})
    requirement = [SkillRequirement(skill="robotics", min_level=4)]
    mandatory = work("M", hours=5, mandatory=True, skills=requirement)
    optional = work("O", hours=5, skills=requirement)
    opportunity = work("C", hours=1, wtype="sales_opportunity", skills=requirement)
    result = PlannerEngine().plan(dataset(
        [mandatory, optional, opportunity],
        people=[qualified, unqualified],
        options=[option("C", "C-A", delivery=5)],
    ))

    assert result.get_decision("M").decision == DecisionType.MANDATORY_INFEASIBLE
    assert result.get_decision("O").decision == DecisionType.DELAY
    assert result.get_decision("C").decision == DecisionType.NO_BID


def test_21_person_total_capacity():
    result = PlannerEngine().plan(dataset([work("A", hours=3), work("B", hours=3)], people=[person(capacity=4)]))
    assert result.person_capacity[0].used_hours <= 4


def test_22_person_daily_capacity():
    result = PlannerEngine().plan(dataset([work("A", hours=4)], people=[person(capacity=4)]))
    by_day = {}
    for entry in result.schedule:
        by_day[entry.date] = by_day.get(entry.date, 0) + entry.hours
    assert max(by_day.values()) <= 1 + 1e-8


def test_23_unavailable_day_has_no_schedule():
    p = person(capacity=3, unavailable=[DateRange(start=date(2026, 1, 2), end=date(2026, 1, 2))])
    result = PlannerEngine().plan(dataset([work("A", hours=3)], people=[p]))
    assert all(entry.date != date(2026, 1, 2) for entry in result.schedule)


def test_24_work_can_span_multiple_days():
    result = PlannerEngine().plan(dataset([work("A", hours=4)], people=[person(capacity=4)]))
    assert len({entry.date for entry in result.schedule}) == 4


def test_25_earliest_start_respected():
    result = PlannerEngine().plan(dataset([work("A", earliest=date(2026, 1, 3))]))
    assert min(entry.date for entry in result.schedule) >= date(2026, 1, 3)


def test_26_dependency_starts_after_predecessor_completion():
    result = PlannerEngine().plan(dataset([work("A"), work("B", deps=["A"])]))
    finish_a = result.get_decision("A").details["completion_date"]
    start_b = min(entry.date for entry in result.schedule if entry.action_id == "B")
    assert start_b > finish_a


def test_27_soft_deadline_can_be_late_with_warning():
    result = PlannerEngine().plan(dataset([work("A", hours=3, due=date(2026, 1, 1))], people=[person(capacity=4)]))
    assert PlannerReasonCode.SCHEDULED_AFTER_DUE_DATE in result.get_decision("A").reason_codes


def test_28_sales_expiry_not_selectable():
    opp = work("OPP", wtype="sales_opportunity", due=date(2025, 12, 31))
    result = PlannerEngine().plan(dataset([opp], options=[option("OPP", "A")]))
    assert "A" not in result.selected_actions and "OPP" in result.no_bid_opportunities


def test_29_shared_resource_capacity():
    res = SharedResource(id="R", name="R", capacity_hours=1, exclusive=False)
    req = [ResourceRequirement(resource_id="R", hours=2)]
    result = PlannerEngine().plan(dataset([work("A", resources=req)], resources=[res]))
    assert "A" not in result.selected_actions


def test_30_exclusive_resource_not_double_booked():
    res = SharedResource(id="R", name="R", capacity_hours=2, exclusive=True)
    req = [ResourceRequirement(resource_id="R", hours=1)]
    data = dataset(
        [work("A", resources=req, revenue=100), work("B", resources=req, revenue=50)],
        people=[person(capacity=2)], resources=[res], start=date(2026, 1, 1), end=date(2026, 1, 1),
    )
    result = PlannerEngine().plan(data)
    assert len(result.resource_schedule) == 1


def test_31_score_orders_optional_feasible_actions():
    data = dataset(
        [work("HIGH", revenue=1000), work("LOW", revenue=10)],
        people=[person(capacity=1)], start=date(2026, 1, 1), end=date(2026, 1, 1),
    )
    assert PlannerEngine().plan(data).selected_actions == ["HIGH"]


def test_32_high_score_cannot_override_hard_constraint():
    high = work("HIGH", revenue=1_000_000, skills=[SkillRequirement(skill="missing", min_level=5)])
    result = PlannerEngine().plan(dataset([high, work("LOW", revenue=1)]))
    assert "HIGH" not in result.selected_actions and "LOW" in result.selected_actions


def test_33_mandatory_score_has_no_artificial_bonus():
    data = dataset([work("M", mandatory=True, revenue=1), work("O", revenue=1000)])
    portfolio = PortfolioEffectsEngine().evaluate(data, PortfolioEffectsEngine.build_context_from_dataset(data))
    commercial = CommercialEvaluationEngine().evaluate(data, portfolio)
    scores = ScoringEngine().evaluate(data, portfolio, commercial)
    assert scores.get_candidate("M").business_value_score < scores.get_candidate("O").business_value_score


def reduction_dataset():
    trigger = work("TRIGGER", hours=1, mandatory=True)
    target = work("TARGET", hours=4, revenue=100)
    effect = PortfolioEffect(
        id="E", trigger="TRIGGER", targets=["TARGET"],
        effect={"type": "hours_reduction", "value": .5},
    )
    return dataset([trigger, target], people=[person(capacity=10)], effects=[effect])


def test_34_portfolio_effective_hours_consumed():
    result = PlannerEngine().plan(reduction_dataset())
    assert result.get_decision("TARGET").details["effective_base_hours"] == 2


def test_35_effect_re_evaluated_after_completion():
    result = PlannerEngine().plan(reduction_dataset())
    assert min(e.date for e in result.schedule if e.action_id == "TARGET") > result.get_decision("TRIGGER").details["completion_date"]


def test_36_planner_is_deterministic():
    data = reduction_dataset()
    assert PlannerEngine().plan(data).model_dump() == PlannerEngine().plan(data).model_dump()


def test_37_canonical_mandatory_closure(canonical_plan):
    assert not canonical_plan.mandatory_infeasible
    assert all(wid in canonical_plan.selected_actions for wid in ["W001", "W002", "W003", "W004", "W005", "W021"])


def test_38_canonical_commercial_exclusivity(canonical_plan, canonical):
    selected = set(canonical_plan.selected_actions)
    for work_id in {option.work_item_id for option in canonical.commercial_options}:
        ids = {option.option_id for option in canonical.commercial_options if option.work_item_id == work_id}
        assert len(ids & selected) <= 1


def test_39_canonical_capacity_not_over_748(canonical_plan):
    assert sum(item.used_hours for item in canonical_plan.person_capacity) <= 748 + 1e-6


def test_40_canonical_plan_smoke(canonical_plan):
    assert canonical_plan.status.value in {"FEASIBLE", "PARTIAL"}
    assert canonical_plan.schedule and canonical_plan.assignments


def test_41_get_plan_api():
    from fastapi.testclient import TestClient
    from app.main import app
    response = TestClient(app).get("/api/v1/plan")
    assert response.status_code == 200 and "decisions" in response.json()


def test_42_canonical_w011c_remains_select_option_when_chosen(canonical):
    canonical_work = next(item for item in canonical.work_items if item.id == "W011")
    canonical_option = next(item for item in canonical.commercial_options if item.option_id == "W011-C")
    subset = canonical.model_copy(update={
        "work_items": [canonical_work],
        "commercial_options": [canonical_option],
        "portfolio_effects": [],
        "shared_resources": [],
    })
    result = PlannerEngine().plan(subset)
    assert result.get_decision("W011-C").decision == DecisionType.SELECT_OPTION
    assert "W011" not in result.no_bid_opportunities
