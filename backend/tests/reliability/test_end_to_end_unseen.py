"""Compact unseen-data pipeline and integrated status tests."""
from __future__ import annotations

import json
from pathlib import Path

from app.decision_engine.cash_flow import CashFlowSimulator
from app.decision_engine.final_validation import (
    FinancialStatus,
    FinalValidationEngine,
    OperationalStatus,
    OverallStatus,
)
from app.decision_engine.planner import PlannerEngine
from app.services.dataset_loader import read_json, validate_json_schema, validate_references

from .factories import run_pipeline

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "data" / "candidate_dataset.schema.json"


def test_unseen_dataset_is_same_schema_and_reference_valid(unseen_dataset):
    raw = unseen_dataset.model_dump(mode="json")
    assert validate_json_schema(raw, read_json(SCHEMA)) == []
    assert validate_references(unseen_dataset) == []


def test_full_pipeline_accepts_noncanonical_ids_skills_languages_and_resources(unseen_dataset):
    result = run_pipeline(unseen_dataset)
    assert len(result.feasibility) == 3
    assert len(result.portfolio.effects) == 2
    assert result.commercial.get_option("PREMIUM_OFFER") is not None
    assert result.scoring.get_candidate("PREMIUM_OFFER") is not None
    assert {"TRIGGER_TASK", "ALPHA_TASK", "PREMIUM_OFFER"} <= set(result.plan.selected_actions)
    assert {usage.resource_id for usage in result.plan.resource_capacity} == {"GPU_CLUSTER"}
    assert result.cash.scenarios
    assert result.final.overall_status == OverallStatus.PLAN_FEASIBLE


def test_unseen_pipeline_outputs_are_internally_consistent(unseen_dataset):
    result = run_pipeline(unseen_dataset)
    selected = set(result.plan.selected_actions)
    scheduled = {entry.action_id for entry in result.plan.schedule}
    assigned = {assignment.action_id for assignment in result.plan.assignments}
    assert selected <= scheduled
    assert selected <= assigned
    assert result.final.executive_summary.selected_count == len(result.plan.selected_actions)
    assert result.final.cash_summary.starting_cash_jpy == unseen_dataset.company.starting_cash_jpy
    assert result.final.operational_status == OperationalStatus.OPERATIONALLY_FEASIBLE
    assert result.final.financial_status == FinancialStatus.CASH_SAFE


def test_entire_unseen_pipeline_requires_no_canonical_identifier(unseen_dataset):
    payload = json.dumps(run_pipeline(unseen_dataset).final.model_dump(mode="json"), sort_keys=True)
    for canonical_prefix in ("W001", "P001", "R001", "W006-A", "W012-A"):
        assert canonical_prefix not in payload


def test_final_validation_does_not_mutate_unseen_upstream_inputs(unseen_dataset):
    plan = PlannerEngine().plan(unseen_dataset)
    cash = CashFlowSimulator().simulate(unseen_dataset, plan)
    before = (
        unseen_dataset.model_dump(),
        plan.model_dump(),
        cash.model_dump(),
    )
    FinalValidationEngine().validate(unseen_dataset, plan, cash)
    assert before == (
        unseen_dataset.model_dump(),
        plan.model_dump(),
        cash.model_dump(),
    )
