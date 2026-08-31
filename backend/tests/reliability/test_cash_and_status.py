"""Exact-JPY cash edges and final integrated status combinations."""
from __future__ import annotations

from app.decision_engine.cash_flow import (
    CashEventType,
    CashFlowSimulator,
    CashScenario,
    ScenarioCashStatus,
)
from app.decision_engine.final_validation import (
    FinancialStatus,
    FinalValidationEngine,
    OperationalStatus,
    OverallStatus,
)
from app.decision_engine.planner import PlannerEngine, ResourceScheduleEntry

from .factories import PLAN_END, PLAN_START, make_dataset, make_option, make_person, make_resource, make_work_item


def _cash(dataset):
    plan = PlannerEngine().plan(dataset)
    return plan, CashFlowSimulator().simulate(dataset, plan)


def test_no_revenue_no_cost_and_null_cash_days_produce_no_work_cash_events():
    dataset = make_dataset(work_items=[make_work_item(
        "NO_CASH_TASK",
        revenue=0,
        direct_cost=0,
        committed=True,
        cash_in_days=None,
    )])
    _, cash = _cash(dataset)
    event_types = {
        event.event_type
        for scenario in cash.scenarios.values()
        for event in scenario.in_horizon_events + scenario.future_events
    }
    assert CashEventType.WORK_CASH_RECEIPT not in event_types
    assert CashEventType.WORK_DIRECT_COST not in event_types


def test_receipt_on_horizon_end_is_in_horizon_but_next_day_is_future():
    end_offset = (PLAN_END - PLAN_START).days
    on_end = make_dataset(work_items=[make_work_item(
        "END_DATE_RECEIPT", hours=1, revenue=100, committed=True, cash_in_days=end_offset,
    )])
    day_after = make_dataset(work_items=[make_work_item(
        "FUTURE_RECEIPT", hours=1, revenue=100, committed=True, cash_in_days=end_offset + 1,
    )])
    _, end_cash = _cash(on_end)
    _, future_cash = _cash(day_after)
    expected_end = end_cash.scenarios[CashScenario.EXPECTED]
    expected_future = future_cash.scenarios[CashScenario.EXPECTED]
    assert any(e.date == PLAN_END and e.event_type == CashEventType.WORK_CASH_RECEIPT for e in expected_end.in_horizon_events)
    assert any(e.date > PLAN_END and e.event_type == CashEventType.WORK_CASH_RECEIPT for e in expected_future.future_events)


def test_uneven_fixed_outflow_reconciles_exactly_in_integer_jpy():
    dataset = make_dataset(work_items=[], fixed_outflow=1_003)
    _, cash = _cash(dataset)
    for scenario in cash.scenarios.values():
        fixed = [e.amount_jpy for e in scenario.in_horizon_events if e.event_type == CashEventType.FIXED_OUTFLOW]
        assert sum(fixed) == 1_003
        assert max(fixed) - min(fixed) <= 1
        assert all(isinstance(amount, int) for amount in fixed)


def test_starting_cash_buffer_boundaries_and_negative_start_are_safe_to_evaluate():
    at_buffer = make_dataset(work_items=[], starting_cash=100, minimum_buffer=100)
    below_buffer = make_dataset(work_items=[], starting_cash=99, minimum_buffer=100)
    negative = make_dataset(work_items=[], starting_cash=-1, minimum_buffer=0)
    assert _cash(at_buffer)[1].scenarios[CashScenario.EXPECTED].status == ScenarioCashStatus.CASH_SAFE
    assert _cash(below_buffer)[1].scenarios[CashScenario.EXPECTED].status == ScenarioCashStatus.BUFFER_BREACH
    assert _cash(negative)[1].scenarios[CashScenario.EXPECTED].status == ScenarioCashStatus.NEGATIVE_CASH


def test_many_future_events_are_preserved_without_affecting_horizon_cash():
    works = [
        make_work_item(
            f"FUTURE_SOURCE_{index}",
            hours=1,
            revenue=100 + index,
            committed=True,
            cash_in_days=30,
        )
        for index in range(8)
    ]
    dataset = make_dataset(
        people=[make_person("FUTURE_TEAM", capacity=20)],
        work_items=works,
        starting_cash=10_000,
    )
    _, cash = _cash(dataset)
    assert {event.source_id for event in cash.future_events} == {work.id for work in works}
    assert cash.scenarios[CashScenario.EXPECTED].total_cash_in_jpy == 0


def test_every_daily_ledger_reconciles_exactly():
    dataset = make_dataset(
        work_items=[make_work_item(
            "RECONCILE_TASK", hours=2, revenue=777, direct_cost=101,
            committed=True, cash_in_days=0,
        )],
        fixed_outflow=1_003,
    )
    _, cash = _cash(dataset)
    for scenario in cash.scenarios.values():
        for day in scenario.timeline:
            assert day.net_change_jpy == day.cash_in_jpy - day.cash_out_jpy
            assert day.closing_cash_jpy == day.opening_cash_jpy + day.net_change_jpy
        assert scenario.ending_cash_jpy == scenario.timeline[-1].closing_cash_jpy


def test_integrated_feasible_safe_is_plan_feasible():
    dataset = make_dataset(work_items=[make_work_item("SAFE_TASK")], starting_cash=1_000)
    result = FinalValidationEngine().validate(dataset, *_cash(dataset))
    assert result.operational_status == OperationalStatus.OPERATIONALLY_FEASIBLE
    assert result.financial_status == FinancialStatus.CASH_SAFE
    assert result.overall_status == OverallStatus.PLAN_FEASIBLE


def test_integrated_partial_safe_is_plan_partial():
    dataset = make_dataset(
        people=[make_person("ONE_HOUR", capacity=1)],
        work_items=[
            make_work_item("HIGH_VALUE", revenue=100),
            make_work_item("LOW_VALUE", revenue=1),
        ],
        start=PLAN_START,
        end=PLAN_START,
        starting_cash=1_000,
    )
    result = FinalValidationEngine().validate(dataset, *_cash(dataset))
    assert result.operational_status == OperationalStatus.OPERATIONALLY_PARTIAL
    assert result.financial_status == FinancialStatus.CASH_SAFE
    assert result.overall_status == OverallStatus.PLAN_PARTIAL


def test_integrated_expected_negative_is_plan_at_risk():
    dataset = make_dataset(work_items=[], starting_cash=1, fixed_outflow=2)
    result = FinalValidationEngine().validate(dataset, *_cash(dataset))
    assert result.financial_status == FinancialStatus.NEGATIVE_CASH
    assert result.overall_status == OverallStatus.PLAN_AT_RISK


def test_integrated_hard_operational_failure_dominates_safe_cash():
    resource = make_resource("EXCLUSIVE_DEVICE", capacity=10, exclusive=True)
    dataset = make_dataset(resources=[resource], work_items=[make_work_item("VALID_TASK")])
    plan, cash = _cash(dataset)
    conflicted = plan.model_copy(update={
        "resource_schedule": [
            ResourceScheduleEntry(date=PLAN_START, resource_id="EXCLUSIVE_DEVICE", action_id="ACTION_ONE", hours=1),
            ResourceScheduleEntry(date=PLAN_START, resource_id="EXCLUSIVE_DEVICE", action_id="ACTION_TWO", hours=1),
        ]
    })
    result = FinalValidationEngine().validate(dataset, conflicted, cash)
    assert result.financial_status == FinancialStatus.CASH_SAFE
    assert result.operational_status == OperationalStatus.OPERATIONALLY_INFEASIBLE
    assert result.overall_status == OverallStatus.PLAN_INFEASIBLE


def test_expected_safe_downside_negative_maps_to_cash_at_risk():
    opportunity = make_work_item("RISKY_SALE", hours=0, work_type="sales_opportunity")
    option = make_option(
        "RISKY_SALE", "RISKY_OFFER", price=100, cost=0,
        delivery_hours=0, probability=0.5, payment_days=0,
    )
    dataset = make_dataset(
        work_items=[opportunity],
        options=[option],
        start=PLAN_START,
        end=PLAN_START,
        starting_cash=50,
        fixed_outflow=75,
        minimum_buffer=0,
    )
    plan, cash = _cash(dataset)
    assert cash.scenarios[CashScenario.EXPECTED].status == ScenarioCashStatus.CASH_SAFE
    assert cash.scenarios[CashScenario.DOWNSIDE].status == ScenarioCashStatus.NEGATIVE_CASH
    assert cash.scenarios[CashScenario.SUCCESS].status == ScenarioCashStatus.CASH_SAFE
    result = FinalValidationEngine().validate(dataset, plan, cash)
    assert result.financial_status == FinancialStatus.CASH_AT_RISK
    assert result.overall_status == OverallStatus.PLAN_AT_RISK


def test_expected_buffer_breach_retains_buffer_breach_aggregate():
    dataset = make_dataset(
        work_items=[],
        starting_cash=100,
        fixed_outflow=1,
        minimum_buffer=100,
    )
    plan, cash = _cash(dataset)
    result = FinalValidationEngine().validate(dataset, plan, cash)
    assert cash.scenarios[CashScenario.EXPECTED].status == ScenarioCashStatus.BUFFER_BREACH
    assert result.financial_status == FinancialStatus.BUFFER_BREACH
