"""Focused Phase 2F cash-flow simulator tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from app.decision_engine.assumptions import AssumptionRegistry
from app.decision_engine.cash_flow import (
    CashEventType,
    CashFlowSimulator,
    CashScenario,
    ScenarioCashStatus,
    prorate_jpy,
)
from app.decision_engine.planner import (
    AllocationType,
    DecisionType,
    PlanDecision,
    PlanResult,
    PlanStatus,
    PlannerEngine,
    ScheduleEntry,
)
from app.domain.models import (
    CandidateDataset,
    CommercialOption,
    Company,
    Enumerations,
    Metadata,
    PortfolioEffect,
    WorkItem,
)
from app.services.dataset_loader import load_dataset

START = date(2026, 1, 1)
END = date(2026, 1, 4)


def work(
    wid: str,
    *,
    revenue: int = 0,
    cost: int = 0,
    cash_days: int | None = None,
    committed: bool = True,
    penalty: int = 0,
) -> WorkItem:
    return WorkItem(
        id=wid,
        title=wid,
        type="delivery",
        mandatory=False,
        committed=committed,
        revenue_jpy=revenue,
        direct_cost_jpy=cost,
        cash_in_days=cash_days,
        required_hours=1,
        earliest_start=START,
        due_date=END,
        late_penalty_jpy_per_day=penalty,
    )


def option(
    work_id: str = "OPP",
    option_id: str = "OPT",
    *,
    price: int = 1000,
    cost: int = 100,
    payment_days: int = 0,
    probability: float = 0.5,
) -> CommercialOption:
    return CommercialOption(
        work_item_id=work_id,
        option_id=option_id,
        label=option_id,
        price_jpy=price,
        direct_cost_jpy=cost,
        delivery_hours=1,
        payment_days=payment_days,
        estimated_win_probability=probability,
        follow_on_value_jpy=0,
    )


def dataset(
    works: list[WorkItem],
    *,
    options: list[CommercialOption] | None = None,
    effects: list[PortfolioEffect] | None = None,
    starting: int = 1000,
    fixed: int = 0,
    buffer: int = 0,
    start: date = START,
    end: date = END,
) -> CandidateDataset:
    return CandidateDataset(
        metadata=Metadata(
            dataset_id="CASH", version="1", planning_start=start,
            planning_end=end, currency="JPY",
        ),
        company=Company(
            name="CashCo", starting_cash_jpy=starting,
            fixed_cash_outflow_jpy=fixed, minimum_cash_buffer_jpy=buffer,
        ),
        people=[],
        customers=[],
        shared_resources=[],
        work_items=works,
        commercial_options=options or [],
        portfolio_effects=effects or [],
        enumerations=Enumerations(),
    )


def work_plan(
    item: WorkItem,
    dates: list[date],
    *,
    delayed: list[str] | None = None,
    no_bid: list[str] | None = None,
    late_days: int = 0,
) -> PlanResult:
    details = {
        "start_date": min(dates),
        "completion_date": max(dates),
        "base_completion_date": max(dates),
        "late_days": late_days,
    }
    return PlanResult(
        status=PlanStatus.PARTIAL,
        decisions=[PlanDecision(
            work_item_id=item.id,
            action_id=item.id,
            decision=DecisionType.DO,
            details=details,
        )],
        schedule=[
            ScheduleEntry(
                date=day, action_id=item.id, person_id="P",
                hours=1, allocation_type=AllocationType.WORK,
            )
            for day in dates
        ],
        selected_actions=[item.id],
        delayed_actions=delayed or [],
        no_bid_opportunities=no_bid or [],
    )


def option_plan(
    work_item: WorkItem,
    selected_option: CommercialOption,
    *,
    base_date: date = START,
    reserved_dates: list[date] | None = None,
) -> PlanResult:
    reserved_dates = reserved_dates or [base_date]
    completion = max([base_date, *reserved_dates])
    return PlanResult(
        status=PlanStatus.PARTIAL,
        decisions=[PlanDecision(
            work_item_id=work_item.id,
            action_id=selected_option.option_id,
            selected_option_id=selected_option.option_id,
            decision=DecisionType.SELECT_OPTION,
            details={
                "start_date": base_date,
                "base_completion_date": base_date,
                "completion_date": completion,
            },
        )],
        schedule=[
            ScheduleEntry(
                date=base_date, action_id=selected_option.option_id,
                person_id="P", hours=1,
                allocation_type=AllocationType.SCHEDULED_BASE_EFFORT,
            ),
            *[
                ScheduleEntry(
                    date=day, action_id=selected_option.option_id,
                    person_id="P", hours=1,
                    allocation_type=AllocationType.RESERVED_DELIVERY,
                )
                for day in reserved_dates
            ],
        ],
        selected_actions=[selected_option.option_id],
    )


def event_total(result, scenario, event_type):
    return result.get_scenario(scenario).event_totals_jpy.get(event_type.value, 0)


def test_01_starting_cash_loaded_from_dataset():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], starting=12345), work_plan(item, [START]))
    assert result.starting_cash_jpy == 12345
    assert result.get_scenario("EXPECTED").timeline[0].opening_cash_jpy == 12345


def test_02_fixed_outflow_exact_total():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], fixed=10), work_plan(item, [START]))
    assert event_total(result, "EXPECTED", CashEventType.FIXED_OUTFLOW) == 10


def test_03_fixed_outflow_prorated_daily():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], fixed=8), work_plan(item, [START]))
    assert [row.cash_out_jpy for row in result.get_scenario("EXPECTED").timeline] == [2, 2, 2, 2]


def test_04_prorating_remainder_is_exact_and_earliest():
    assert prorate_jpy(10, [START, date(2026, 1, 2), date(2026, 1, 3)]) == [
        (START, 4), (date(2026, 1, 2), 3), (date(2026, 1, 3), 3)
    ]


def test_05_work_direct_cost_prorating():
    item = work("W", cost=5)
    result = CashFlowSimulator().simulate(dataset([item]), work_plan(item, [START, date(2026, 1, 2)]))
    events = [e.amount_jpy for e in result.get_scenario("EXPECTED").in_horizon_events if e.event_type == CashEventType.WORK_DIRECT_COST]
    assert events == [3, 2]


def test_06_commercial_cost_uses_reserved_delivery_dates():
    opp = work("OPP", cost=999, committed=False)
    opt = option(cost=100, probability=1)
    result = CashFlowSimulator().simulate(
        dataset([opp], options=[opt]),
        option_plan(opp, opt, reserved_dates=[date(2026, 1, 2), date(2026, 1, 3)]),
    )
    dates = [e.date for e in result.get_scenario("SUCCESS").in_horizon_events if e.event_type == CashEventType.COMMERCIAL_DELIVERY_COST]
    assert dates == [date(2026, 1, 2), date(2026, 1, 3)]


def test_07_parent_direct_cost_not_double_counted_for_option():
    opp = work("OPP", cost=999, committed=False)
    opt = option(cost=100, probability=1)
    result = CashFlowSimulator().simulate(dataset([opp], options=[opt]), option_plan(opp, opt))
    success = result.get_scenario("SUCCESS")
    assert event_total(result, "SUCCESS", CashEventType.COMMERCIAL_DELIVERY_COST) == 100
    assert CashEventType.WORK_DIRECT_COST.value not in success.event_totals_jpy


def test_08_work_receipt_after_completion_plus_delay():
    item = work("W", revenue=500, cash_days=2)
    result = CashFlowSimulator().simulate(dataset([item]), work_plan(item, [START]))
    receipt = next(e for e in result.get_scenario("EXPECTED").in_horizon_events if e.event_type == CashEventType.WORK_CASH_RECEIPT)
    assert receipt.date == date(2026, 1, 3)


def test_09_commercial_receipt_after_payment_days():
    opp = work("OPP", committed=False)
    opt = option(payment_days=1, probability=1)
    result = CashFlowSimulator().simulate(
        dataset([opp], options=[opt]),
        option_plan(opp, opt, reserved_dates=[date(2026, 1, 2)]),
    )
    receipt = next(e for e in result.get_scenario("SUCCESS").in_horizon_events if e.event_type == CashEventType.COMMERCIAL_CASH_RECEIPT)
    assert receipt.date == date(2026, 1, 3)


def test_10_outside_horizon_receipt_excluded_from_balance():
    item = work("W", revenue=500, cash_days=10)
    result = CashFlowSimulator().simulate(dataset([item]), work_plan(item, [START]))
    expected = result.get_scenario("EXPECTED")
    assert expected.total_cash_in_jpy == 0 and expected.ending_cash_jpy == 1000


def test_11_future_event_is_retained():
    item = work("W", revenue=500, cash_days=10)
    result = CashFlowSimulator().simulate(dataset([item]), work_plan(item, [START]))
    assert result.get_scenario("EXPECTED").future_events[0].amount_jpy == 500


def test_12_revenue_is_not_immediate_cash():
    item = work("W", revenue=500, cash_days=2)
    result = CashFlowSimulator().simulate(dataset([item]), work_plan(item, [START]))
    assert result.get_scenario("EXPECTED").timeline[0].cash_in_jpy == 0


def commercial_result(price=1000, cost=100, probability=.5):
    opp = work("OPP", committed=False)
    opt = option(price=price, cost=cost, probability=probability)
    result = CashFlowSimulator().simulate(dataset([opp], options=[opt]), option_plan(opp, opt))
    return result


def test_13_expected_commercial_revenue_probability():
    assert event_total(commercial_result(), "EXPECTED", CashEventType.COMMERCIAL_CASH_RECEIPT) == 500


def test_14_success_commercial_cash_full_price():
    assert event_total(commercial_result(), "SUCCESS", CashEventType.COMMERCIAL_CASH_RECEIPT) == 1000


def test_15_downside_commercial_revenue_zero():
    result = commercial_result()
    receipt = next(e for e in result.get_scenario("DOWNSIDE").in_horizon_events if e.event_type == CashEventType.COMMERCIAL_CASH_RECEIPT)
    assert receipt.amount_jpy == 0


def test_16_expected_conditional_delivery_cost():
    assert event_total(commercial_result(), "EXPECTED", CashEventType.COMMERCIAL_DELIVERY_COST) == 50


def test_17_downside_conditional_delivery_cost_zero():
    assert event_total(commercial_result(), "DOWNSIDE", CashEventType.COMMERCIAL_DELIVERY_COST) == 0


def cash_effect_dataset(include_trigger=True, starting=1000, fixed=0, buffer=0):
    trigger = work("TRIGGER", cash_days=1)
    effect = PortfolioEffect(
        id="CASH", trigger="TRIGGER", targets=["company_cash"],
        effect={"type": "cash_inflow", "value_jpy": 100, "probability": .5},
    )
    data = dataset([trigger], effects=[effect], starting=starting, fixed=fixed, buffer=buffer)
    plan = work_plan(trigger, [START]) if include_trigger else PlanResult(status=PlanStatus.PARTIAL)
    return data, plan


def test_18_cash_effect_inactive_without_completed_trigger():
    data, plan = cash_effect_dataset(False)
    result = CashFlowSimulator().simulate(data, plan)
    assert event_total(result, "EXPECTED", CashEventType.PORTFOLIO_CASH_INFLOW) == 0


def test_19_cash_effect_expected_value():
    data, plan = cash_effect_dataset()
    assert event_total(CashFlowSimulator().simulate(data, plan), "EXPECTED", CashEventType.PORTFOLIO_CASH_INFLOW) == 50


def test_20_cash_effect_success_value():
    data, plan = cash_effect_dataset()
    assert event_total(CashFlowSimulator().simulate(data, plan), "SUCCESS", CashEventType.PORTFOLIO_CASH_INFLOW) == 100


def test_21_cash_effect_downside_zero():
    data, plan = cash_effect_dataset()
    result = CashFlowSimulator().simulate(data, plan)
    event = next(e for e in result.get_scenario("DOWNSIDE").in_horizon_events if e.event_type == CashEventType.PORTFOLIO_CASH_INFLOW)
    assert event.amount_jpy == 0


def test_22_cash_effect_timing_uses_trigger_completion_delay():
    data, plan = cash_effect_dataset()
    result = CashFlowSimulator().simulate(data, plan)
    event = next(e for e in result.get_scenario("EXPECTED").in_horizon_events if e.event_type == CashEventType.PORTFOLIO_CASH_INFLOW)
    assert event.date == date(2026, 1, 2)


def test_23_minimum_cash_buffer_safe():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], starting=10, fixed=4, buffer=5), work_plan(item, [START]))
    assert result.get_scenario("EXPECTED").status == ScenarioCashStatus.CASH_SAFE


def test_24_buffer_breach_detection():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], starting=10, fixed=8, buffer=5), work_plan(item, [START]))
    assert result.get_scenario("EXPECTED").status == ScenarioCashStatus.BUFFER_BREACH


def test_25_first_buffer_breach_date():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], starting=10, fixed=8, buffer=5), work_plan(item, [START]))
    assert result.get_scenario("EXPECTED").first_buffer_breach_date == date(2026, 1, 3)


def test_26_minimum_cash_date_and_value():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], starting=10, fixed=8), work_plan(item, [START]))
    expected = result.get_scenario("EXPECTED")
    assert (expected.minimum_cash_jpy, expected.minimum_cash_date) == (2, END)


def test_27_negative_cash_detection():
    item = work("W")
    result = CashFlowSimulator().simulate(dataset([item], starting=2, fixed=4), work_plan(item, [START]))
    assert result.get_scenario("EXPECTED").status == ScenarioCashStatus.NEGATIVE_CASH


def test_28_expected_safe_downside_unsafe():
    data, plan = cash_effect_dataset(starting=10, fixed=6, buffer=5)
    data.portfolio_effects[0].effect["value_jpy"] = 4
    data.portfolio_effects[0].effect["probability"] = .5
    result = CashFlowSimulator().simulate(data, plan)
    assert result.get_scenario("EXPECTED").status == ScenarioCashStatus.CASH_SAFE
    assert result.get_scenario("DOWNSIDE").status == ScenarioCashStatus.BUFFER_BREACH


def test_29_true_zero_receipt_distinct_from_missing_timing():
    zero = work("ZERO", revenue=0, cash_days=0)
    missing = work("MISS", revenue=100, cash_days=None)
    plan = PlanResult(
        status=PlanStatus.PARTIAL,
        decisions=[
            *work_plan(zero, [START]).decisions,
            *work_plan(missing, [START]).decisions,
        ],
        schedule=[
            *work_plan(zero, [START]).schedule,
            *work_plan(missing, [START]).schedule,
        ],
        selected_actions=["ZERO", "MISS"],
    )
    result = CashFlowSimulator().simulate(dataset([zero, missing]), plan)
    receipts = [e for e in result.get_scenario("EXPECTED").in_horizon_events if e.event_type == CashEventType.WORK_CASH_RECEIPT]
    assert [(e.source_id, e.amount_jpy) for e in receipts] == [("ZERO", 0)]


def test_30_late_penalty_applied_when_policy_is_explicit():
    item = work("W", penalty=10)
    plan = work_plan(item, [START], late_days=2)
    assumptions = AssumptionRegistry(late_penalty_cash_timing="at_completion")
    result = CashFlowSimulator(assumptions).simulate(dataset([item]), plan)
    assert event_total(result, "EXPECTED", CashEventType.LATE_PENALTY) == 20


def test_31_selected_plan_remains_unchanged():
    item = work("W", cost=100)
    plan = work_plan(item, [START])
    before = deepcopy(plan.model_dump())
    CashFlowSimulator().simulate(dataset([item]), plan)
    assert plan.model_dump() == before


def test_32_delayed_work_produces_no_cash_event():
    selected = work("A")
    delayed = work("B", revenue=100, cost=50, cash_days=0)
    plan = work_plan(selected, [START], delayed=["B"])
    result = CashFlowSimulator().simulate(dataset([selected, delayed]), plan)
    assert all(e.source_id != "B" for e in result.get_scenario("EXPECTED").in_horizon_events)


def test_33_no_bid_produces_no_option_cash():
    selected = work("A")
    opp = work("OPP", committed=False)
    opt = option()
    plan = work_plan(selected, [START], no_bid=["OPP"])
    result = CashFlowSimulator().simulate(dataset([selected, opp], options=[opt]), plan)
    assert all(e.source_id != "OPT" for e in result.get_scenario("EXPECTED").in_horizon_events)


def test_34_repeated_run_is_deterministic():
    item = work("W", revenue=100, cost=7, cash_days=1)
    data = dataset([item], fixed=11)
    plan = work_plan(item, [START, date(2026, 1, 2)])
    assert CashFlowSimulator().simulate(data, plan).model_dump() == CashFlowSimulator().simulate(data, plan).model_dump()


def test_35_integer_jpy_reconciliation():
    item = work("W", cost=7)
    result = CashFlowSimulator().simulate(dataset([item], fixed=11), work_plan(item, [START, date(2026, 1, 2), date(2026, 1, 3)]))
    assert event_total(result, "EXPECTED", CashEventType.FIXED_OUTFLOW) == 11
    assert event_total(result, "EXPECTED", CashEventType.WORK_DIRECT_COST) == 7


@pytest.fixture(scope="module")
def canonical():
    root = Path(__file__).resolve().parents[2]
    data = load_dataset(root / "data/candidate_dataset.json", root / "data/candidate_dataset.schema.json")
    plan = PlannerEngine().plan(data)
    result = CashFlowSimulator().simulate(data, plan)
    return data, plan, result


def test_36_canonical_w021_cash_scenarios(canonical):
    _, _, result = canonical
    assert event_total(result, "EXPECTED", CashEventType.PORTFOLIO_CASH_INFLOW) == 3_230_000
    assert event_total(result, "SUCCESS", CashEventType.PORTFOLIO_CASH_INFLOW) == 3_800_000
    assert event_total(result, "DOWNSIDE", CashEventType.PORTFOLIO_CASH_INFLOW) == 0


def test_37_canonical_w012_rejected_when_qualified_capacity_cannot_meet_expiry(canonical):
    _, plan, result = canonical
    future = [e for e in result.get_scenario("EXPECTED").future_events if e.source_id == "W012-A"]
    assert future == []
    assert "W012" in plan.no_bid_opportunities


def test_38_canonical_fixed_outflow(canonical):
    _, _, result = canonical
    assert event_total(result, "EXPECTED", CashEventType.FIXED_OUTFLOW) == 8_000_000


def test_39_canonical_four_week_ledger(canonical):
    _, _, result = canonical
    assert len(result.get_scenario("EXPECTED").timeline) == 28


def test_40_canonical_plan_not_replanned(canonical):
    _, plan, result = canonical
    assert result.operational_plan_status == plan.status.value
    assert "W012" in plan.no_bid_opportunities


def test_41_cash_flow_api():
    from fastapi.testclient import TestClient
    from app.main import app
    response = TestClient(app).post("/api/v1/cash-flow", json={})
    assert response.status_code == 200
    assert len(response.json()["scenarios"]["EXPECTED"]["timeline"]) == 28
