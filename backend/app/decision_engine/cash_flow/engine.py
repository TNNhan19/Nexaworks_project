"""Deterministic, exact-JPY Phase 2F cash-flow simulator."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS, AssumptionRegistry
from app.decision_engine.commercial import CommercialEvaluationEngine, CommercialEvaluationResult
from app.decision_engine.planner import AllocationType, DecisionType, PlanResult
from app.decision_engine.portfolio import PortfolioEffectsEngine, PortfolioEffectsResult
from app.domain.models import CandidateDataset

from .models import (
    CashEvent,
    CashFinding,
    CashFlowResult,
    CashScenarioResult,
    DailyCashLedger,
)
from .proration import exact_jpy, probability_weighted_jpy, prorate_jpy
from .reason_codes import (
    CashDirection,
    CashEventType,
    CashReasonCode,
    CashScenario,
    CashSourceType,
    OverallCashStatus,
    ScenarioCashStatus,
)


def _dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=index) for index in range((end - start).days + 1)]


def _as_date(value: date | str | None) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None


class CashFlowSimulator:
    """Evaluate a supplied operational plan without changing its decisions."""

    def __init__(self, assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS) -> None:
        self.assumptions = assumptions

    def simulate(
        self,
        dataset: CandidateDataset,
        plan: PlanResult,
        *,
        portfolio_result: PortfolioEffectsResult | None = None,
        commercial_result: CommercialEvaluationResult | None = None,
    ) -> CashFlowResult:
        selected_decisions = [
            decision for decision in plan.decisions
            if decision.decision in {
                DecisionType.DO,
                DecisionType.ENABLING_PREREQUISITE,
                DecisionType.SELECT_OPTION,
            }
        ]
        completed_ids = frozenset(decision.work_item_id for decision in selected_decisions)
        if portfolio_result is None:
            portfolio_engine = PortfolioEffectsEngine()
            context = portfolio_engine.build_context_from_dataset(
                dataset,
                completed_work_item_ids=completed_ids,
                selected_work_item_ids=completed_ids,
            )
            portfolio_result = portfolio_engine.evaluate(dataset, context)
        if commercial_result is None:
            commercial_result = CommercialEvaluationEngine().evaluate(
                dataset, portfolio_result, completed_ids=completed_ids
            )

        self.dataset = dataset
        self.plan = plan
        self.portfolio = portfolio_result
        self.commercial = commercial_result
        self.work = {item.id: item for item in dataset.work_items}
        self.options = {item.option_id: item for item in dataset.commercial_options}
        self.horizon = _dates(dataset.metadata.planning_start, dataset.metadata.planning_end)
        self.selected_decisions = selected_decisions
        self.completion_dates = {
            decision.work_item_id: _as_date(decision.details.get("completion_date"))
            for decision in selected_decisions
        }

        warnings = self._semantic_warnings()
        scenarios: dict[CashScenario, CashScenarioResult] = {}
        reasons = [
            CashFinding(
                code=CashReasonCode.STARTING_CASH_LOADED,
                details={"starting_cash_jpy": dataset.company.starting_cash_jpy},
            ),
            CashFinding(
                code=CashReasonCode.FIXED_OUTFLOW_PRORATED,
                details={
                    "total_jpy": dataset.company.fixed_cash_outflow_jpy,
                    "days": len(self.horizon),
                    "policy": self.assumptions.fixed_outflow_timing,
                },
            ),
            CashFinding(
                code=CashReasonCode.CASH_TIMING_ASSUMPTION_USED,
                details=self._assumptions_used(),
            ),
        ]
        for scenario in CashScenario:
            scenario_result = self._simulate_scenario(scenario)
            scenarios[scenario] = scenario_result
            if scenario_result.buffer_breach_dates:
                reasons.append(CashFinding(
                    code=CashReasonCode.MINIMUM_BUFFER_BREACH,
                    scenario=scenario,
                    details={
                        "first_breach_date": scenario_result.first_buffer_breach_date,
                        "days_below_buffer": scenario_result.days_below_buffer,
                        "minimum_cash_jpy": scenario_result.minimum_cash_jpy,
                    },
                ))
            if scenario_result.negative_cash_dates:
                reasons.append(CashFinding(
                    code=CashReasonCode.NEGATIVE_CASH,
                    scenario=scenario,
                    details={
                        "first_negative_date": scenario_result.negative_cash_dates[0],
                        "minimum_cash_jpy": scenario_result.minimum_cash_jpy,
                    },
                ))
        reasons.extend(self._trace_findings(scenarios))

        overall = (
            OverallCashStatus.CASH_SAFE
            if all(result.status == ScenarioCashStatus.CASH_SAFE for result in scenarios.values())
            else OverallCashStatus.CASH_AT_RISK
        )
        future_events = sorted(
            [event for result in scenarios.values() for event in result.future_events],
            key=lambda event: (event.date, event.scenario.value, event.event_id),
        )
        return CashFlowResult(
            overall_status=overall,
            operational_plan_status=plan.status.value,
            starting_cash_jpy=exact_jpy(dataset.company.starting_cash_jpy),
            minimum_buffer_jpy=exact_jpy(dataset.company.minimum_cash_buffer_jpy),
            scenarios=scenarios,
            future_events=future_events,
            reasons=reasons,
            warnings=warnings,
            assumptions_used=self._assumptions_used(),
        )

    def _assumptions_used(self) -> dict[str, str]:
        return {
            "fixed_outflow_timing": self.assumptions.fixed_outflow_timing,
            "direct_cost_timing": self.assumptions.direct_cost_timing,
            "work_cash_receipt_timing": self.assumptions.work_cash_receipt_timing,
            "work_revenue_cash_policy": self.assumptions.work_revenue_cash_policy,
            "commercial_receipt_timing": self.assumptions.commercial_receipt_timing,
            "commercial_direct_cost_timing": self.assumptions.commercial_direct_cost_timing,
            "commercial_direct_cost_probability": self.assumptions.commercial_direct_cost_probability,
            "commercial_cost_source_policy": self.assumptions.commercial_cost_source_policy,
            "late_penalty_cash_timing": self.assumptions.late_penalty_cash_timing,
        }

    def _semantic_warnings(self) -> list[CashFinding]:
        warnings: list[CashFinding] = []
        selected_work_ids = {decision.work_item_id for decision in self.selected_decisions}
        for decision in self.selected_decisions:
            item = self.work[decision.work_item_id]
            if (
                decision.decision != DecisionType.SELECT_OPTION
                and exact_jpy(item.revenue_jpy) > 0
                and not item.committed
            ):
                warnings.append(CashFinding(
                    code=CashReasonCode.UNCOMMITTED_WORK_REVENUE_EXCLUDED,
                    source_id=item.id,
                    details={
                        "revenue_jpy": exact_jpy(item.revenue_jpy),
                        "committed": item.committed,
                        "dictionary_semantics": "work revenue is associated with committed work",
                    },
                ))
            if (
                decision.decision != DecisionType.SELECT_OPTION
                and item.committed
                and exact_jpy(item.revenue_jpy) > 0
                and item.cash_in_days is None
            ):
                warnings.append(CashFinding(
                    code=CashReasonCode.CASH_TIMING_UNAVAILABLE,
                    source_id=item.id,
                    details={"field": "cash_in_days", "revenue_jpy": exact_jpy(item.revenue_jpy)},
                ))
            if decision.decision == DecisionType.SELECT_OPTION:
                option_id = decision.selected_option_id or decision.action_id
                metrics = self.commercial.get_option(option_id)
                if metrics is not None and metrics.payment_days is None:
                    warnings.append(CashFinding(
                        code=CashReasonCode.CASH_TIMING_UNAVAILABLE,
                        source_id=option_id,
                        details={"field": "payment_days"},
                    ))
            late_days = int(decision.details.get("late_days", 0) or 0)
            penalty = exact_jpy(item.late_penalty_jpy_per_day)
            if (
                late_days > 0
                and penalty > 0
                and self.assumptions.late_penalty_cash_timing
                == "not_included_without_cash_semantics"
            ):
                warnings.append(CashFinding(
                    code=CashReasonCode.LATE_PENALTY_CASH_SEMANTICS_UNSUPPORTED,
                    source_id=item.id,
                    details={
                        "late_days": late_days,
                        "late_penalty_jpy_per_day": penalty,
                        "potential_penalty_jpy": late_days * penalty,
                    },
                ))
        for work_item_id in self.plan.delayed_actions:
            warnings.append(CashFinding(
                code=CashReasonCode.DELAYED_ACTION_EXCLUDED,
                source_id=work_item_id,
                details={"selected_for_cash_flow": work_item_id in selected_work_ids},
            ))
        for work_item_id in self.plan.no_bid_opportunities:
            warnings.append(CashFinding(
                code=CashReasonCode.NO_BID_EXCLUDED,
                source_id=work_item_id,
            ))
        return warnings

    def _trace_findings(
        self,
        scenarios: dict[CashScenario, CashScenarioResult],
    ) -> list[CashFinding]:
        findings: list[CashFinding] = []
        for scenario, result in scenarios.items():
            direct_cost_total = sum(
                amount for key, amount in result.event_totals_jpy.items()
                if key in {
                    CashEventType.WORK_DIRECT_COST.value,
                    CashEventType.COMMERCIAL_DELIVERY_COST.value,
                }
            )
            if direct_cost_total:
                findings.append(CashFinding(
                    code=CashReasonCode.DIRECT_COST_PRORATED,
                    scenario=scenario,
                    details={"total_jpy": direct_cost_total},
                ))
            for event in [*result.in_horizon_events, *result.future_events]:
                if event.event_type in {
                    CashEventType.WORK_CASH_RECEIPT,
                    CashEventType.COMMERCIAL_CASH_RECEIPT,
                    CashEventType.PORTFOLIO_CASH_INFLOW,
                }:
                    findings.append(CashFinding(
                        code=(
                            CashReasonCode.CASH_RECEIPT_OUTSIDE_HORIZON
                            if event.outside_horizon
                            else CashReasonCode.CASH_RECEIPT_SCHEDULED
                        ),
                        source_id=event.source_id,
                        scenario=scenario,
                        details={
                            "event_date": event.date,
                            "amount_jpy": event.amount_jpy,
                            "event_type": event.event_type.value,
                        },
                    ))
                if (
                    scenario == CashScenario.EXPECTED
                    and event.event_type in {
                        CashEventType.COMMERCIAL_CASH_RECEIPT,
                        CashEventType.PORTFOLIO_CASH_INFLOW,
                    }
                ):
                    findings.append(CashFinding(
                        code=CashReasonCode.EXPECTED_PROBABILISTIC_INFLOW,
                        source_id=event.source_id,
                        scenario=scenario,
                        details={"amount_jpy": event.amount_jpy, "probability": event.probability},
                    ))
                if (
                    scenario == CashScenario.DOWNSIDE
                    and event.direction == CashDirection.INFLOW
                    and event.probability is not None
                    and event.amount_jpy == 0
                ):
                    findings.append(CashFinding(
                        code=CashReasonCode.DOWNSIDE_PROBABILISTIC_INFLOW_ZERO,
                        source_id=event.source_id,
                        scenario=scenario,
                        details={"probability": event.probability},
                    ))
                if event.event_type == CashEventType.LATE_PENALTY:
                    findings.append(CashFinding(
                        code=CashReasonCode.LATE_PENALTY_APPLIED,
                        source_id=event.source_id,
                        scenario=scenario,
                        details={"amount_jpy": event.amount_jpy, "event_date": event.date},
                    ))
        return findings

    def _simulate_scenario(self, scenario: CashScenario) -> CashScenarioResult:
        events = self._events_for_scenario(scenario)
        in_horizon = sorted(
            [event for event in events if not event.outside_horizon],
            key=lambda event: (event.date, event.event_id),
        )
        future = sorted(
            [event for event in events if event.outside_horizon],
            key=lambda event: (event.date, event.event_id),
        )
        by_date: dict[date, list[CashEvent]] = {day: [] for day in self.horizon}
        for event in in_horizon:
            by_date[event.date].append(event)

        opening = exact_jpy(self.dataset.company.starting_cash_jpy)
        minimum_buffer = exact_jpy(self.dataset.company.minimum_cash_buffer_jpy)
        timeline: list[DailyCashLedger] = []
        event_totals: dict[str, int] = {}
        for day in self.horizon:
            day_events = sorted(by_date[day], key=lambda event: event.event_id)
            cash_in = sum(
                event.amount_jpy for event in day_events
                if event.direction == CashDirection.INFLOW
            )
            cash_out = sum(
                event.amount_jpy for event in day_events
                if event.direction == CashDirection.OUTFLOW
            )
            for event in day_events:
                key = event.event_type.value
                event_totals[key] = event_totals.get(key, 0) + event.amount_jpy
            closing = opening + cash_in - cash_out
            timeline.append(DailyCashLedger(
                date=day,
                opening_cash_jpy=opening,
                cash_in_jpy=cash_in,
                cash_out_jpy=cash_out,
                net_change_jpy=cash_in - cash_out,
                closing_cash_jpy=closing,
                minimum_buffer_jpy=minimum_buffer,
                buffer_headroom_jpy=closing - minimum_buffer,
                buffer_breach=closing < minimum_buffer,
                negative_cash=closing < 0,
                events=day_events,
            ))
            opening = closing

        buffer_dates = [row.date for row in timeline if row.buffer_breach]
        negative_dates = [row.date for row in timeline if row.negative_cash]
        minimum_row = min(timeline, key=lambda row: (row.closing_cash_jpy, row.date))
        status = (
            ScenarioCashStatus.NEGATIVE_CASH if negative_dates
            else ScenarioCashStatus.BUFFER_BREACH if buffer_dates
            else ScenarioCashStatus.CASH_SAFE
        )
        return CashScenarioResult(
            scenario=scenario,
            status=status,
            timeline=timeline,
            in_horizon_events=in_horizon,
            future_events=future,
            total_cash_in_jpy=sum(row.cash_in_jpy for row in timeline),
            total_cash_out_jpy=sum(row.cash_out_jpy for row in timeline),
            event_totals_jpy=event_totals,
            minimum_cash_jpy=minimum_row.closing_cash_jpy,
            minimum_cash_date=minimum_row.date,
            ending_cash_jpy=timeline[-1].closing_cash_jpy,
            first_buffer_breach_date=buffer_dates[0] if buffer_dates else None,
            days_below_buffer=len(buffer_dates),
            buffer_breach_dates=buffer_dates,
            negative_cash_dates=negative_dates,
        )

    def _events_for_scenario(self, scenario: CashScenario) -> list[CashEvent]:
        events: list[CashEvent] = []
        fixed_total = exact_jpy(self.dataset.company.fixed_cash_outflow_jpy)
        for index, (day, amount) in enumerate(prorate_jpy(fixed_total, self.horizon)):
            events.append(self._event(
                scenario, CashEventType.FIXED_OUTFLOW, CashSourceType.COMPANY,
                "company", day, amount, CashDirection.OUTFLOW, True,
                self.assumptions.fixed_outflow_timing, index=index,
                evidence={"declared_total_jpy": fixed_total, "horizon_days": len(self.horizon)},
            ))

        for decision in self.selected_decisions:
            item = self.work[decision.work_item_id]
            if decision.decision == DecisionType.SELECT_OPTION:
                self._add_commercial_events(events, scenario, decision)
            else:
                self._add_work_events(events, scenario, decision)
            self._add_late_penalty(events, scenario, decision)
        self._add_portfolio_cash_events(events, scenario)
        return events

    def _action_dates(
        self,
        action_id: str,
        allocation_types: Iterable[AllocationType],
    ) -> list[date]:
        allowed = set(allocation_types)
        return sorted({
            entry.date for entry in self.plan.schedule
            if entry.action_id == action_id and entry.allocation_type in allowed
        })

    def _add_work_events(self, events: list[CashEvent], scenario: CashScenario, decision) -> None:
        item = self.work[decision.work_item_id]
        execution_dates = self._action_dates(decision.action_id, [AllocationType.WORK])
        cost = exact_jpy(item.direct_cost_jpy)
        if cost > 0 and execution_dates:
            for index, (day, amount) in enumerate(prorate_jpy(cost, execution_dates)):
                events.append(self._event(
                    scenario, CashEventType.WORK_DIRECT_COST, CashSourceType.WORK_ITEM,
                    item.id, day, amount, CashDirection.OUTFLOW, True,
                    self.assumptions.direct_cost_timing, index=index,
                    evidence={
                        "declared_direct_cost_jpy": cost,
                        "execution_dates": [value.isoformat() for value in execution_dates],
                    },
                ))

        if item.committed and item.cash_in_days is not None:
            completion = self.completion_dates.get(item.id)
            if completion is not None:
                receipt_date = completion + timedelta(days=item.cash_in_days)
                amount = exact_jpy(item.revenue_jpy)
                events.append(self._event(
                    scenario, CashEventType.WORK_CASH_RECEIPT, CashSourceType.WORK_ITEM,
                    item.id, receipt_date, amount, CashDirection.INFLOW, True,
                    self.assumptions.work_cash_receipt_timing,
                    evidence={
                        "revenue_jpy": amount,
                        "completion_date": completion.isoformat(),
                        "cash_in_days": item.cash_in_days,
                        "committed": True,
                    },
                ))

    def _scenario_commercial_amount(
        self, scenario: CashScenario, full_amount: int, probability: float
    ) -> int:
        if scenario == CashScenario.SUCCESS:
            return full_amount
        if scenario == CashScenario.EXPECTED:
            return probability_weighted_jpy(full_amount, probability)
        return 0

    def _add_commercial_events(self, events: list[CashEvent], scenario: CashScenario, decision) -> None:
        option_id = decision.selected_option_id or decision.action_id
        metrics = self.commercial.get_option(option_id)
        if metrics is None:
            return
        probability = float(metrics.win_probability or 0.0)
        reserved_dates = self._action_dates(option_id, [AllocationType.RESERVED_DELIVERY])
        full_cost = exact_jpy(metrics.direct_cost_jpy or 0)
        scenario_cost = self._scenario_commercial_amount(scenario, full_cost, probability)
        if reserved_dates and (full_cost > 0 or scenario_cost > 0):
            for index, (day, amount) in enumerate(prorate_jpy(scenario_cost, reserved_dates)):
                events.append(self._event(
                    scenario, CashEventType.COMMERCIAL_DELIVERY_COST,
                    CashSourceType.COMMERCIAL_OPTION, option_id, day, amount,
                    CashDirection.OUTFLOW, scenario == CashScenario.SUCCESS,
                    self.assumptions.commercial_direct_cost_timing,
                    probability=probability,
                    index=index,
                    evidence={
                        "full_direct_cost_jpy": full_cost,
                        "conditional_on_win": True,
                        "parent_work_direct_cost_excluded": True,
                    },
                ))

        reference_date = (
            max(reserved_dates) if reserved_dates
            else _as_date(decision.details.get("completion_date"))
        )
        if reference_date is None or metrics.payment_days is None:
            return
        receipt_date = reference_date + timedelta(days=metrics.payment_days)
        full_price = exact_jpy(metrics.price_jpy or 0)
        scenario_price = self._scenario_commercial_amount(
            scenario, full_price, probability
        )
        events.append(self._event(
            scenario, CashEventType.COMMERCIAL_CASH_RECEIPT,
            CashSourceType.COMMERCIAL_OPTION, option_id, receipt_date,
            scenario_price, CashDirection.INFLOW,
            scenario == CashScenario.SUCCESS,
            self.assumptions.commercial_receipt_timing,
            probability=probability,
            evidence={
                "full_price_jpy": full_price,
                "delivery_reference_date": reference_date.isoformat(),
                "payment_days": metrics.payment_days,
            },
        ))

    def _add_portfolio_cash_events(
        self, events: list[CashEvent], scenario: CashScenario
    ) -> None:
        for effect in self.portfolio.cash_effects:
            completion = self.completion_dates.get(effect.trigger_work_item_id)
            trigger = self.work.get(effect.trigger_work_item_id)
            if not effect.trigger_satisfied or completion is None or trigger is None:
                continue
            if trigger.cash_in_days is None:
                continue
            event_date = completion + timedelta(days=trigger.cash_in_days)
            if scenario == CashScenario.SUCCESS:
                amount = exact_jpy(effect.success_case_cash_inflow_jpy)
            elif scenario == CashScenario.EXPECTED:
                amount = exact_jpy(effect.expected_cash_inflow_jpy)
            else:
                amount = exact_jpy(effect.downside_case_cash_inflow_jpy)
            events.append(self._event(
                scenario, CashEventType.PORTFOLIO_CASH_INFLOW,
                CashSourceType.PORTFOLIO_EFFECT, effect.effect_id,
                event_date, amount, CashDirection.INFLOW,
                scenario == CashScenario.SUCCESS,
                "trigger_completion_plus_trigger_cash_in_days",
                probability=effect.probability,
                evidence={
                    "trigger_work_item_id": effect.trigger_work_item_id,
                    "trigger_completion_date": completion.isoformat(),
                    "cash_in_days": trigger.cash_in_days,
                    "full_cash_inflow_jpy": exact_jpy(effect.cash_inflow_jpy),
                    "not_new_revenue": True,
                },
            ))

    def _add_late_penalty(self, events: list[CashEvent], scenario: CashScenario, decision) -> None:
        if self.assumptions.late_penalty_cash_timing != "at_completion":
            return
        item = self.work[decision.work_item_id]
        late_days = int(decision.details.get("late_days", 0) or 0)
        penalty_per_day = exact_jpy(item.late_penalty_jpy_per_day)
        completion = _as_date(decision.details.get("completion_date"))
        if late_days <= 0 or penalty_per_day <= 0 or completion is None:
            return
        events.append(self._event(
            scenario, CashEventType.LATE_PENALTY, CashSourceType.WORK_ITEM,
            item.id, completion, late_days * penalty_per_day,
            CashDirection.OUTFLOW, True, "at_completion",
            evidence={
                "late_days": late_days,
                "late_penalty_jpy_per_day": penalty_per_day,
            },
        ))

    def _event(
        self,
        scenario: CashScenario,
        event_type: CashEventType,
        source_type: CashSourceType,
        source_id: str,
        event_date: date,
        amount: int,
        direction: CashDirection,
        deterministic: bool,
        timing_basis: str,
        *,
        probability: float | None = None,
        index: int = 0,
        evidence: dict | None = None,
    ) -> CashEvent:
        outside = not (
            self.dataset.metadata.planning_start
            <= event_date
            <= self.dataset.metadata.planning_end
        )
        return CashEvent(
            event_id=f"{scenario.value}:{event_type.value}:{source_id}:{event_date.isoformat()}:{index}",
            date=event_date,
            source_type=source_type,
            source_id=source_id,
            event_type=event_type,
            scenario=scenario,
            amount_jpy=amount,
            direction=direction,
            deterministic=deterministic,
            probability=probability,
            timing_basis=timing_basis,
            outside_horizon=outside,
            evidence=evidence or {},
        )
