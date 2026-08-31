"""Phase 2G explanation builder.

Converts upstream PlanResult + CashFlowResult + validation findings into
structured DecisionExplanation and ExplanationRecord objects.

No natural-language strings are generated here.  All outputs use
ExplanationCode values that the frontend i18n layer translates.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.decision_engine.cash_flow.models import CashFlowResult
from app.decision_engine.cash_flow.reason_codes import (
    CashDirection,
    CashEventType,
    CashScenario,
    ScenarioCashStatus,
)
from app.decision_engine.planner.models import PlanResult
from app.decision_engine.planner.reason_codes import (
    DecisionType,
    PlannerReasonCode,
)
from app.domain.models import CandidateDataset

from .models import (
    CashSummary,
    DecisionExplanation,
    ExplanationRecord,
    FutureReceiptSummary,
    ScenarioCashSummary,
)
from .reason_codes import ExplanationCode, FindingSeverity, SourcePhase

# Mapping from planner delay codes to 2G codes
_DELAY_CODE_MAP: dict[str, ExplanationCode] = {
    PlannerReasonCode.DELAYED_CAPACITY_LIMIT.value: ExplanationCode.DELAYED_CAPACITY_LIMIT,
    PlannerReasonCode.DELAYED_RESOURCE_CONFLICT.value: ExplanationCode.DELAYED_RESOURCE_LIMIT,
    PlannerReasonCode.DELAYED_PREREQUISITE_NOT_SCHEDULABLE.value: ExplanationCode.DELAYED_PREREQUISITE_NOT_SELECTED,
    PlannerReasonCode.DELAYED_HARD_CONSTRAINT.value: ExplanationCode.DELAYED_HARD_CONSTRAINT,
    PlannerReasonCode.NO_BID_CAPACITY_CONSTRAINT.value: ExplanationCode.DELAYED_CAPACITY_LIMIT,
    PlannerReasonCode.NO_BID_NO_FEASIBLE_OPTION.value: ExplanationCode.DELAYED_HARD_CONSTRAINT,
}


def _rec(
    code: ExplanationCode,
    severity: FindingSeverity,
    source_phase: SourcePhase = SourcePhase.FINAL_VALIDATION,
    source_id: str | None = None,
    action_id: str | None = None,
    **evidence: Any,
) -> ExplanationRecord:
    return ExplanationRecord(
        code=code,
        severity=severity,
        source_phase=source_phase,
        source_id=source_id,
        action_id=action_id,
        evidence=dict(evidence),
    )


# ---------------------------------------------------------------------------
# Decision explanations
# ---------------------------------------------------------------------------

def build_decision_explanations(
    dataset: CandidateDataset,
    plan: PlanResult,
    cash_result: CashFlowResult,
) -> list[DecisionExplanation]:
    """Build one DecisionExplanation per plan decision."""
    work_map = {item.id: item for item in dataset.work_items}
    option_map = {opt.option_id: opt for opt in dataset.commercial_options}
    horizon_end = dataset.metadata.planning_end

    # Build future receipt source IDs from EXPECTED scenario
    future_receipt_sources: dict[str, list[ExplanationRecord]] = {}
    if CashScenario.EXPECTED in cash_result.scenarios:
        exp = cash_result.scenarios[CashScenario.EXPECTED]
        for ev in exp.future_events:
            if ev.direction == CashDirection.INFLOW and ev.amount_jpy > 0:
                rec = _rec(
                    ExplanationCode.FUTURE_RECEIPT_OUTSIDE_HORIZON,
                    FindingSeverity.INFO,
                    source_phase=SourcePhase.CASH_FLOW,
                    source_id=ev.source_id,
                    event_date=str(ev.date),
                    event_type=ev.event_type.value,
                    expected_amount_jpy=ev.amount_jpy,
                )
                future_receipt_sources.setdefault(ev.source_id, []).append(rec)

    explanations: list[DecisionExplanation] = []
    for dec in plan.decisions:
        findings: list[ExplanationRecord] = []
        item = work_map.get(dec.work_item_id)

        if dec.decision == DecisionType.DO:
            findings.append(_rec(
                ExplanationCode.WORK_DO,
                FindingSeverity.INFO,
                source_phase=SourcePhase.PLANNER,
                source_id=dec.work_item_id,
                action_id=dec.action_id,
                mandatory=item.mandatory if item else False,
                reason_codes=[rc.value for rc in dec.reason_codes],
                **{k: str(v) if isinstance(v, date) else v
                   for k, v in dec.details.items()},
            ))
            # Late warning
            if PlannerReasonCode.SCHEDULED_AFTER_DUE_DATE in dec.reason_codes:
                findings.append(_rec(
                    ExplanationCode.DEADLINE_LATE,
                    FindingSeverity.WARNING,
                    source_phase=SourcePhase.PLANNER,
                    source_id=dec.work_item_id,
                    action_id=dec.action_id,
                    late_days=dec.details.get("late_days"),
                    due_date=str(item.due_date) if item else None,
                ))

        elif dec.decision == DecisionType.ENABLING_PREREQUISITE:
            findings.append(_rec(
                ExplanationCode.ENABLING_PREREQUISITE,
                FindingSeverity.INFO,
                source_phase=SourcePhase.PLANNER,
                source_id=dec.work_item_id,
                action_id=dec.action_id,
                prerequisite_ids=dec.prerequisite_ids,
            ))

        elif dec.decision == DecisionType.SELECT_OPTION:
            option_id = dec.selected_option_id or dec.action_id
            opt = option_map.get(option_id)
            completion = dec.details.get("completion_date")
            cd = (completion if isinstance(completion, date)
                  else date.fromisoformat(str(completion)) if completion else None)
            payment_days = opt.payment_days if opt else None
            receipt_date = None
            if cd is not None and payment_days is not None:
                from datetime import timedelta
                receipt_date = cd + timedelta(days=payment_days)

            findings.append(_rec(
                ExplanationCode.OPTION_SELECTED,
                FindingSeverity.INFO,
                source_phase=SourcePhase.PLANNER,
                source_id=dec.work_item_id,
                action_id=option_id,
                option_id=option_id,
                delivery_reservation_completion=str(cd) if cd else None,
                payment_days=payment_days,
                receipt_date=str(receipt_date) if receipt_date else None,
                reason_codes=[rc.value for rc in dec.reason_codes],
                unlock_trigger_ids=dec.unlock_trigger_ids,
            ))
            # Future payment warning
            if receipt_date is not None and receipt_date > horizon_end:
                findings.append(_rec(
                    ExplanationCode.COMMERCIAL_PAYMENT_OUTSIDE_HORIZON,
                    FindingSeverity.WARNING,
                    source_phase=SourcePhase.CASH_FLOW,
                    source_id=option_id,
                    action_id=dec.action_id,
                    receipt_date=str(receipt_date),
                    horizon_end=str(horizon_end),
                    note="no in-horizon cash benefit from this commercial option",
                ))
            # Future receipt records from cash engine
            for fr in future_receipt_sources.get(option_id, []):
                findings.append(fr)

        elif dec.decision == DecisionType.DELAY:
            delay_code = ExplanationCode.WORK_DELAYED
            for rc in dec.reason_codes:
                mapped = _DELAY_CODE_MAP.get(rc.value)
                if mapped:
                    delay_code = mapped
                    break
            findings.append(_rec(
                ExplanationCode.WORK_DELAYED,
                FindingSeverity.INFO,
                source_phase=SourcePhase.PLANNER,
                source_id=dec.work_item_id,
                action_id=dec.action_id,
                delay_reason=delay_code.value,
                reason_codes=[rc.value for rc in dec.reason_codes],
            ))

        elif dec.decision == DecisionType.NO_BID:
            findings.append(_rec(
                ExplanationCode.PLANNER_NO_BID,
                FindingSeverity.INFO,
                source_phase=SourcePhase.PLANNER,
                source_id=dec.work_item_id,
                action_id=dec.action_id,
                reason_codes=[rc.value for rc in dec.reason_codes],
                attempt_failures=dec.details.get("attempt_failures", {}),
            ))
            # Future receipts (should be empty but forward anyway)
            for fr in future_receipt_sources.get(dec.action_id, []):
                findings.append(fr)

        elif dec.decision == DecisionType.MANDATORY_INFEASIBLE:
            findings.append(_rec(
                ExplanationCode.MANDATORY_WORK_INFEASIBLE,
                FindingSeverity.ERROR,
                source_phase=SourcePhase.PLANNER,
                source_id=dec.work_item_id,
                action_id=dec.action_id,
                failure_code=dec.details.get("failure_code"),
            ))

        # Forward future receipt evidence for work items (W001, W002, etc.)
        for fr in future_receipt_sources.get(dec.work_item_id, []):
            if dec.decision in {DecisionType.DO, DecisionType.ENABLING_PREREQUISITE}:
                findings.append(fr)

        explanations.append(DecisionExplanation(
            work_item_id=dec.work_item_id,
            action_id=dec.action_id,
            decision=dec.decision.value,
            reason_codes=[rc.value for rc in dec.reason_codes],
            findings=findings,
            details={
                k: str(v) if isinstance(v, date) else v
                for k, v in dec.details.items()
            },
        ))
    return explanations


# ---------------------------------------------------------------------------
# Cash summary and findings
# ---------------------------------------------------------------------------

def build_cash_summary(
    dataset: CandidateDataset,
    cash_result: CashFlowResult,
) -> tuple[CashSummary, list[ExplanationRecord]]:
    """Build CashSummary and cash-related ExplanationRecords."""
    from .reason_codes import FinancialStatus

    # Determine financial_status (worst scenario wins)
    worst_status = FinancialStatus.CASH_SAFE
    scenario_summaries: list[ScenarioCashSummary] = []

    for scenario_key in [CashScenario.EXPECTED, CashScenario.DOWNSIDE, CashScenario.SUCCESS]:
        if scenario_key not in cash_result.scenarios:
            continue
        s = cash_result.scenarios[scenario_key]
        scenario_summaries.append(ScenarioCashSummary(
            scenario=scenario_key.value,
            status=s.status.value,
            ending_cash_jpy=s.ending_cash_jpy,
            minimum_cash_jpy=s.minimum_cash_jpy,
            minimum_cash_date=s.minimum_cash_date,
            first_buffer_breach_date=s.first_buffer_breach_date,
            days_below_buffer=s.days_below_buffer,
            negative_cash=bool(s.negative_cash_dates),
        ))
        if s.status == ScenarioCashStatus.NEGATIVE_CASH:
            worst_status = FinancialStatus.NEGATIVE_CASH
        elif s.status == ScenarioCashStatus.BUFFER_BREACH and worst_status != FinancialStatus.NEGATIVE_CASH:
            worst_status = FinancialStatus.BUFFER_BREACH
        elif worst_status == FinancialStatus.CASH_SAFE and cash_result.overall_status.value == "CASH_AT_RISK":
            worst_status = FinancialStatus.CASH_AT_RISK

    # Cash findings
    findings: list[ExplanationRecord] = []
    exp_s = cash_result.scenarios.get(CashScenario.EXPECTED)
    dn_s = cash_result.scenarios.get(CashScenario.DOWNSIDE)
    su_s = cash_result.scenarios.get(CashScenario.SUCCESS)

    if exp_s and exp_s.negative_cash_dates:
        findings.append(_rec(
            ExplanationCode.NEGATIVE_CASH_EXPECTED,
            FindingSeverity.CRITICAL,
            source_phase=SourcePhase.CASH_FLOW,
            ending_cash_jpy=exp_s.ending_cash_jpy,
            first_negative_date=str(exp_s.negative_cash_dates[0]),
            minimum_cash_jpy=exp_s.minimum_cash_jpy,
        ))

    if dn_s and dn_s.negative_cash_dates:
        findings.append(_rec(
            ExplanationCode.NEGATIVE_CASH_DOWNSIDE,
            FindingSeverity.CRITICAL,
            source_phase=SourcePhase.CASH_FLOW,
            ending_cash_jpy=dn_s.ending_cash_jpy,
            first_negative_date=str(dn_s.negative_cash_dates[0]),
            minimum_cash_jpy=dn_s.minimum_cash_jpy,
        ))

    if su_s and su_s.negative_cash_dates:
        findings.append(_rec(
            ExplanationCode.NEGATIVE_CASH_SUCCESS,
            FindingSeverity.ERROR,
            source_phase=SourcePhase.CASH_FLOW,
            ending_cash_jpy=su_s.ending_cash_jpy,
            first_negative_date=str(su_s.negative_cash_dates[0]),
        ))

    if exp_s and exp_s.first_buffer_breach_date:
        findings.append(_rec(
            ExplanationCode.CASH_BUFFER_BREACH,
            FindingSeverity.WARNING,
            source_phase=SourcePhase.CASH_FLOW,
            scenario="EXPECTED",
            first_buffer_breach_date=str(exp_s.first_buffer_breach_date),
            days_below_buffer=exp_s.days_below_buffer,
            minimum_buffer_jpy=cash_result.minimum_buffer_jpy,
        ))

    # CASH_TIMING_MISMATCH: substantial future receipts but in-horizon cash unsafe
    horizon_out_total = 0
    future_receipts: list[FutureReceiptSummary] = []
    seen_future: set[tuple[str, str]] = set()
    if exp_s:
        for ev in exp_s.future_events:
            if ev.direction == CashDirection.INFLOW and ev.amount_jpy > 0:
                horizon_out_total += ev.amount_jpy
                key = (ev.source_id, ev.event_type.value)
                if key not in seen_future:
                    seen_future.add(key)
                    future_receipts.append(FutureReceiptSummary(
                        source_id=ev.source_id,
                        event_type=ev.event_type.value,
                        date=ev.date,
                        expected_amount_jpy=ev.amount_jpy,
                    ))

    if horizon_out_total > 0 and worst_status in {
        FinancialStatus.NEGATIVE_CASH, FinancialStatus.BUFFER_BREACH, FinancialStatus.CASH_AT_RISK
    }:
        in_horizon_out = (exp_s.total_cash_out_jpy if exp_s else 0)
        in_horizon_in = (exp_s.total_cash_in_jpy if exp_s else 0)
        findings.append(_rec(
            ExplanationCode.CASH_TIMING_MISMATCH,
            FindingSeverity.WARNING,
            source_phase=SourcePhase.CASH_FLOW,
            in_horizon_outflows_jpy=in_horizon_out,
            in_horizon_receipts_jpy=in_horizon_in,
            future_receipts_total_expected_jpy=horizon_out_total,
            expected_ending_cash_jpy=exp_s.ending_cash_jpy if exp_s else None,
            future_receipt_sources=[fr.source_id for fr in future_receipts],
        ))

    summary = CashSummary(
        starting_cash_jpy=cash_result.starting_cash_jpy,
        minimum_buffer_jpy=cash_result.minimum_buffer_jpy,
        financial_status=worst_status,
        scenarios=scenario_summaries,
        future_receipts=sorted(future_receipts, key=lambda f: f.date),
        findings=findings,
    )
    return summary, findings


# ---------------------------------------------------------------------------
# Forward planner warnings
# ---------------------------------------------------------------------------

def forward_planner_warnings(plan: PlanResult) -> list[ExplanationRecord]:
    """Convert PlannerWarning objects into ExplanationRecords (INFO/WARNING level)."""
    results: list[ExplanationRecord] = []
    for pw in plan.warnings:
        results.append(_rec(
            ExplanationCode.WORK_DELAYED if pw.code == PlannerReasonCode.DELAYED_CAPACITY_LIMIT
            else ExplanationCode.DEADLINE_LATE if pw.code == PlannerReasonCode.SCHEDULED_AFTER_DUE_DATE
            else ExplanationCode.PERSON_CAPACITY_EXCEEDED if pw.code == PlannerReasonCode.PERSON_CAPACITY_EXCEEDED
            else ExplanationCode.RESOURCE_EXCLUSIVITY_VIOLATION if pw.code == PlannerReasonCode.RESOURCE_CONFLICT
            else ExplanationCode.DEPENDENCY_ORDER_VIOLATION if pw.code == PlannerReasonCode.DEPENDENCY_CYCLE_DETECTED
            else ExplanationCode.WORK_DO,
            FindingSeverity.WARNING,
            source_phase=SourcePhase.PLANNER,
            action_id=pw.action_id,
            planner_code=pw.code.value,
            **pw.details,
        ))
    return results
