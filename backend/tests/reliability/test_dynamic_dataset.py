"""Dynamic-size and non-canonical capability tests."""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.decision_engine.commercial import CommercialEvaluationEngine
from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.planner import DecisionType, PlannerEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine
from app.decision_engine.scoring import ScoringEngine
from app.domain.models import SkillRequirement

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


@pytest.mark.parametrize("people_count", [1, 3, 12])
def test_dynamic_people_counts(people_count: int):
    people = [make_person(f"EMPLOYEE_{index}", capacity=10) for index in range(people_count)]
    dataset = make_dataset(people=people, work_items=[make_work_item("TASK_ONLY", hours=1)])
    result = FeasibilityEngine().check_all(dataset)
    assert result[0].capacity.total_team_capacity_hours == people_count * 10
    assert result[0].status == FeasibilityStatus.FEASIBLE


@pytest.mark.parametrize("work_count", [1, 5, 31])
def test_dynamic_work_item_counts(work_count: int):
    works = [make_work_item(f"TASK_DYNAMIC_{index:02d}", hours=1) for index in range(work_count)]
    dataset = make_dataset(
        people=[make_person("ELASTIC_TEAM", capacity=work_count + 1)],
        work_items=works,
    )
    feasibility = FeasibilityEngine().check_all(dataset)
    plan = PlannerEngine().plan(dataset)
    assert len(feasibility) == work_count
    assert len(plan.decisions) == work_count
    assert set(plan.selected_actions) == {work.id for work in works}


@pytest.mark.parametrize("option_count", [0, 1, 5])
def test_dynamic_commercial_option_counts(option_count: int):
    opportunity = make_work_item("OPEN_MARKET", hours=0, work_type="sales_opportunity")
    options = [
        make_option("OPEN_MARKET", f"BESPOKE_OFFER_{index}", delivery_hours=0, price=index)
        for index in range(option_count)
    ]
    dataset = make_dataset(work_items=[opportunity], options=options)
    portfolio_engine = PortfolioEffectsEngine()
    portfolio = portfolio_engine.evaluate(
        dataset,
        portfolio_engine.build_context_from_dataset(dataset),
    )
    commercial = CommercialEvaluationEngine().evaluate(dataset, portfolio)
    scoring = ScoringEngine().evaluate(dataset, portfolio, commercial)
    plan = PlannerEngine().plan(dataset)

    expected_candidates = option_count if option_count else 1
    assert len(scoring.candidates) == expected_candidates
    assert sum(d.decision == DecisionType.SELECT_OPTION for d in plan.decisions) <= 1
    if option_count:
        assert len(commercial.opportunities[0].options) == option_count
    else:
        assert commercial.opportunities == []


@pytest.mark.parametrize("effect_count", [0, 4])
def test_dynamic_portfolio_effect_counts(effect_count: int):
    trigger = make_work_item("SOURCE_TRIGGER", hours=1)
    target = make_work_item("TARGET_WORK", hours=10)
    effects = [
        make_effect(
            f"REDUCTION_{index}",
            trigger="SOURCE_TRIGGER",
            targets=["TARGET_WORK"],
            effect_type="hours_reduction",
            value=0.1,
        )
        for index in range(effect_count)
    ]
    dataset = make_dataset(work_items=[trigger, target], effects=effects)
    engine = PortfolioEffectsEngine()
    context = engine.build_context_from_dataset(
        dataset,
        completed_work_item_ids=frozenset({"SOURCE_TRIGGER"}),
    )
    result = engine.evaluate(dataset, context)
    assert len(result.effects) == effect_count
    expected_hours = 10 * (0.9 ** effect_count) if effect_count else 10
    assert result.get_effective_hours("TARGET_WORK", 10) == pytest.approx(expected_hours)


@pytest.mark.parametrize("resource_count", [0, 1, 4])
def test_dynamic_shared_resource_counts(resource_count: int):
    resources = [make_resource(f"ARBITRARY_RESOURCE_{index}") for index in range(resource_count)]
    dataset = make_dataset(resources=resources, work_items=[make_work_item("RESOURCE_FREE_TASK")])
    result = FeasibilityEngine().check_all(dataset)[0]
    assert len(dataset.shared_resources) == resource_count
    assert result.status == FeasibilityStatus.FEASIBLE


def test_unseen_skills_are_dynamic_and_team_coverage_is_per_requirement():
    people = [
        make_person("ROBOT_EXPERT", skills={"robotics": 3}),
        make_person("LEGAL_EXPERT", skills={"legal_review": 2}),
    ]
    task = make_work_item(
        "CROSS_DOMAIN_TASK",
        skills=[
            SkillRequirement(skill="robotics", min_level=3),
            SkillRequirement(skill="legal_review", min_level=2),
        ],
    )
    result = FeasibilityEngine().check_all(make_dataset(people=people, work_items=[task]))[0]
    assert result.status == FeasibilityStatus.FEASIBLE
    assert {coverage.skill for coverage in result.skill_coverage} == {"robotics", "legal_review"}


def test_same_skill_levels_are_never_summed():
    people = [
        make_person("FORENSICS_A", skills={"forensics": 2}),
        make_person("FORENSICS_B", skills={"forensics": 2}),
    ]
    task = make_work_item(
        "FORENSICS_TASK",
        skills=[SkillRequirement(skill="forensics", min_level=3)],
    )
    result = FeasibilityEngine().check_all(make_dataset(people=people, work_items=[task]))[0]
    assert result.status == FeasibilityStatus.INFEASIBLE


@pytest.mark.parametrize("language", ["EN", "JA", "VI", "FR"])
def test_workforce_languages_are_not_limited_to_ui_locales(language: str):
    person = make_person("LANGUAGE_SPECIALIST", languages=[language])
    task = make_work_item("LANGUAGE_TASK", languages=[language])
    result = FeasibilityEngine().check_all(make_dataset(people=[person], work_items=[task]))[0]
    assert result.status == FeasibilityStatus.FEASIBLE


def test_deadline_and_horizon_dates_are_dataset_driven():
    later_start = PLAN_START + timedelta(days=2)
    task = make_work_item("LATE_START_TASK", earliest=later_start, due=PLAN_END)
    plan = PlannerEngine().plan(make_dataset(work_items=[task]))
    assert min(entry.date for entry in plan.schedule) >= later_start
