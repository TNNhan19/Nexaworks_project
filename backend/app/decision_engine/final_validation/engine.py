"""Phase 2G Final Validation Engine.

Integrates Phase 2E (PlanResult) + Phase 2F (CashFlowResult) into a single
FinalDecisionResult with structured validation findings and explanations.

Critical rules:
- NEVER mutates plan or cash_result.
- NEVER reruns the planner or cash simulator.
- NEVER hard-codes work item IDs or monetary values.
- Deterministic: same inputs produce identical output.
"""
from __future__ import annotations

from typing import Any

from app.decision_engine.assumptions import AssumptionRegistry, DEFAULT_ASSUMPTIONS
from app.decision_engine.cash_flow.models import CashFlowResult
from app.decision_engine.cash_flow.reason_codes import CashScenario, ScenarioCashStatus
from app.decision_engine.planner.models import PlanResult
from app.decision_engine.planner.reason_codes import DecisionType, PlanStatus
from app.domain.models import CandidateDataset

from .explainer import (
    build_cash_summary,
    build_decision_explanations,
    forward_planner_warnings,
)
from .models import (
    CapacitySummary,
    ExecutiveSummary,
    ExplanationRecord,
    FinalDecisionResult,
    MandatoryItemOutcome,
    MandatorySummary,
    PersonCapacitySummary,
    ResourceSummary,
    ResourceUsageSummary,
)
from .reason_codes import (
    ExplanationCode,
    FindingSeverity,
    FinancialStatus,
    OperationalStatus,
    OverallStatus,
    SourcePhase,
)
from .validators import (
    validate_commercial_exclusivity,
    validate_daily_capacity,
    validate_dependency_ordering,
    validate_earliest_start,
    validate_language_coverage,
    validate_mandatory_work,
    validate_option_unlock_and_expiry,
    validate_person_capacity,
    validate_resource_capacity,
    validate_resource_exclusivity,
    validate_skill_coverage,
    validate_unavailable_days,
)


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


class FinalValidationEngine:
    """Integrate upstream phase results into a final structured decision result.

    Usage::

        engine = FinalValidationEngine()
        result = engine.validate(dataset, plan, cash_result)
    """

    def __init__(self, assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS) -> None:
        self.assumptions = assumptions

    def validate(
        self,
        dataset: CandidateDataset,
        plan: PlanResult,
        cash_result: CashFlowResult,
    ) -> FinalDecisionResult:
        """Produce the integrated FinalDecisionResult.

        Parameters
        ----------
        dataset:
            The canonical CandidateDataset (never mutated).
        plan:
            Frozen PlanResult from Phase 2E (never mutated).
        cash_result:
            Frozen CashFlowResult from Phase 2F (never mutated).
        """
        # ------------------------------------------------------------------
        # 1. Run all validation checks
        # ------------------------------------------------------------------
        all_findings: list[ExplanationRecord] = []

        mandatory_findings = validate_mandatory_work(dataset, plan)
        dep_findings = validate_dependency_ordering(dataset, plan)
        skill_findings = validate_skill_coverage(dataset, plan)
        lang_findings = validate_language_coverage(dataset, plan)
        capacity_findings = validate_person_capacity(dataset, plan)
        daily_findings = validate_daily_capacity(dataset, plan)
        unavail_findings = validate_unavailable_days(dataset, plan)
        resource_cap_findings = validate_resource_capacity(dataset, plan)
        exclusivity_findings = validate_resource_exclusivity(dataset, plan)
        commercial_excl_findings = validate_commercial_exclusivity(dataset, plan)
        option_expiry_findings = validate_option_unlock_and_expiry(dataset, plan)
        earliest_findings = validate_earliest_start(dataset, plan)
        planner_warnings = forward_planner_warnings(plan)

        structural_findings = (
            mandatory_findings
            + dep_findings
            + skill_findings
            + lang_findings
            + capacity_findings
            + daily_findings
            + unavail_findings
            + resource_cap_findings
            + exclusivity_findings
            + commercial_excl_findings
            + option_expiry_findings
            + earliest_findings
        )
        all_findings.extend(structural_findings)
        all_findings.extend(planner_warnings)

        # ------------------------------------------------------------------
        # 2. Determine operational status
        # ------------------------------------------------------------------
        hard_recheck_failures = [
            f for f in structural_findings
            if f.severity in {FindingSeverity.CRITICAL, FindingSeverity.ERROR}
        ]
        # MANDATORY_WORK_OMITTED elevates to AT_RISK, not INFEASIBLE
        # (the planner may not have been able to handle it, not a fundamental impossibility)
        omitted_mandatory = [
            f for f in mandatory_findings
            if f.code == ExplanationCode.MANDATORY_WORK_OMITTED
        ]
        infeasible_recheck = [
            f for f in hard_recheck_failures
            if f.code not in {ExplanationCode.MANDATORY_WORK_OMITTED,
                               ExplanationCode.MANDATORY_WORK_INFEASIBLE}
        ]

        if plan.status == PlanStatus.INFEASIBLE or infeasible_recheck:
            operational_status = OperationalStatus.OPERATIONALLY_INFEASIBLE
        elif plan.mandatory_infeasible or omitted_mandatory:
            operational_status = OperationalStatus.OPERATIONALLY_AT_RISK
        elif plan.status == PlanStatus.PARTIAL or plan.delayed_actions or plan.no_bid_opportunities:
            operational_status = OperationalStatus.OPERATIONALLY_PARTIAL
        else:
            operational_status = OperationalStatus.OPERATIONALLY_FEASIBLE

        # ------------------------------------------------------------------
        # 3. Build cash summary and determine financial status
        # ------------------------------------------------------------------
        cash_summary, cash_findings = build_cash_summary(dataset, cash_result)
        financial_status = cash_summary.financial_status
        all_findings.extend(cash_findings)

        # ------------------------------------------------------------------
        # 4. Determine overall status
        # ------------------------------------------------------------------
        overall_status = _compute_overall_status(operational_status, financial_status)

        # ------------------------------------------------------------------
        # 5. Overall-level explanation records
        # ------------------------------------------------------------------
        if operational_status in {
            OperationalStatus.OPERATIONALLY_FEASIBLE,
            OperationalStatus.OPERATIONALLY_PARTIAL,
        }:
            all_findings.append(_rec(
                ExplanationCode.PLAN_OPERATIONALLY_VALID
                if operational_status == OperationalStatus.OPERATIONALLY_FEASIBLE
                else ExplanationCode.PLAN_OPERATIONALLY_PARTIAL,
                FindingSeverity.INFO,
                source_phase=SourcePhase.FINAL_VALIDATION,
                plan_status=plan.status.value,
                selected_count=len(plan.selected_actions),
                delayed_count=len(plan.delayed_actions),
                no_bid_count=len(plan.no_bid_opportunities),
            ))
        elif operational_status == OperationalStatus.OPERATIONALLY_INFEASIBLE:
            all_findings.append(_rec(
                ExplanationCode.PLAN_OPERATIONALLY_INFEASIBLE,
                FindingSeverity.CRITICAL,
                source_phase=SourcePhase.FINAL_VALIDATION,
                plan_status=plan.status.value,
                hard_failure_count=len(infeasible_recheck),
            ))

        if financial_status in {
            FinancialStatus.NEGATIVE_CASH,
            FinancialStatus.BUFFER_BREACH,
            FinancialStatus.CASH_AT_RISK,
        }:
            # Build evidence from cash result fields (never hard-coded constants)
            exp_s = cash_result.scenarios.get(CashScenario.EXPECTED)
            dn_s = cash_result.scenarios.get(CashScenario.DOWNSIDE)
            su_s = cash_result.scenarios.get(CashScenario.SUCCESS)
            future_source_ids = [f.source_id for f in cash_summary.future_receipts]
            all_findings.append(_rec(
                ExplanationCode.PLAN_FINANCIALLY_AT_RISK,
                FindingSeverity.CRITICAL if financial_status == FinancialStatus.NEGATIVE_CASH
                else FindingSeverity.ERROR,
                source_phase=SourcePhase.CASH_FLOW,
                starting_cash_jpy=cash_result.starting_cash_jpy,
                expected_ending_cash_jpy=exp_s.ending_cash_jpy if exp_s else None,
                downside_ending_cash_jpy=dn_s.ending_cash_jpy if dn_s else None,
                success_ending_cash_jpy=su_s.ending_cash_jpy if su_s else None,
                first_expected_buffer_breach_date=str(exp_s.first_buffer_breach_date)
                    if exp_s and exp_s.first_buffer_breach_date else None,
                important_future_receipts=future_source_ids,
            ))
        else:
            all_findings.append(_rec(
                ExplanationCode.PLAN_FINANCIALLY_SAFE,
                FindingSeverity.INFO,
                source_phase=SourcePhase.CASH_FLOW,
                overall_cash_status=cash_result.overall_status.value,
            ))

        # ------------------------------------------------------------------
        # 6. Build decision explanations
        # ------------------------------------------------------------------
        decision_explanations = build_decision_explanations(dataset, plan, cash_result)

        # ------------------------------------------------------------------
        # 7. Build mandatory summary
        # ------------------------------------------------------------------
        mandatory_summary = _build_mandatory_summary(dataset, plan)

        # ------------------------------------------------------------------
        # 8. Build capacity and resource summaries
        # ------------------------------------------------------------------
        capacity_summary = _build_capacity_summary(plan, capacity_findings)
        resource_summary = _build_resource_summary(plan, resource_cap_findings + exclusivity_findings)

        # ------------------------------------------------------------------
        # 9. Classify critical issues and warnings
        # ------------------------------------------------------------------
        critical_issues = [
            f for f in all_findings
            if f.severity in {FindingSeverity.CRITICAL, FindingSeverity.ERROR}
        ]
        warnings = [
            f for f in all_findings
            if f.severity == FindingSeverity.WARNING
        ]

        # ------------------------------------------------------------------
        # 10. Build executive summary
        # ------------------------------------------------------------------
        exp_s = cash_result.scenarios.get(CashScenario.EXPECTED)
        dn_s = cash_result.scenarios.get(CashScenario.DOWNSIDE)
        su_s = cash_result.scenarios.get(CashScenario.SUCCESS)
        min_cash_jpy = min(
            (s.minimum_cash_jpy for s in cash_result.scenarios.values()),
            default=None,
        )
        min_cash_date = None
        if min_cash_jpy is not None:
            for s in cash_result.scenarios.values():
                if s.minimum_cash_jpy == min_cash_jpy:
                    min_cash_date = s.minimum_cash_date
                    break

        major_risks = _major_risks(overall_status, financial_status, mandatory_summary)
        major_strengths = _major_strengths(plan, mandatory_summary, capacity_summary)

        executive_summary = ExecutiveSummary(
            plan_status=overall_status.value,
            operational_status=operational_status.value,
            financial_status=financial_status.value,
            selected_count=len(plan.selected_actions),
            delayed_count=len(plan.delayed_actions),
            no_bid_count=len(plan.no_bid_opportunities),
            mandatory_total=mandatory_summary.total_mandatory,
            mandatory_scheduled_count=mandatory_summary.scheduled_count,
            mandatory_infeasible_count=mandatory_summary.infeasible_count,
            total_capacity_hours=capacity_summary.total_capacity_hours,
            total_used_hours=capacity_summary.total_used_hours,
            total_remaining_hours=capacity_summary.total_remaining_hours,
            expected_ending_cash_jpy=exp_s.ending_cash_jpy if exp_s else None,
            downside_ending_cash_jpy=dn_s.ending_cash_jpy if dn_s else None,
            success_ending_cash_jpy=su_s.ending_cash_jpy if su_s else None,
            minimum_cash_jpy=min_cash_jpy,
            minimum_cash_date=min_cash_date,
            first_buffer_breach_date=(
                exp_s.first_buffer_breach_date if exp_s else None
            ),
            major_risks=major_risks,
            major_strengths=major_strengths,
        )

        return FinalDecisionResult(
            overall_status=overall_status,
            operational_status=operational_status,
            financial_status=financial_status,
            executive_summary=executive_summary,
            mandatory_summary=mandatory_summary,
            capacity_summary=capacity_summary,
            resource_summary=resource_summary,
            cash_summary=cash_summary,
            decision_explanations=decision_explanations,
            validations=structural_findings,
            warnings=warnings,
            critical_issues=critical_issues,
            explanation_records=all_findings,
            source_versions={
                "feasibility": "2A",
                "portfolio": "2B",
                "commercial": "2C",
                "scoring": "2D",
                "planner": "2E",
                "cash_flow": "2F",
                "final_validation": "2G",
            },
            assumptions_used=self.assumptions.model_dump(),
        )


# ---------------------------------------------------------------------------
# Status computation helpers
# ---------------------------------------------------------------------------

def _compute_overall_status(
    operational: OperationalStatus,
    financial: FinancialStatus,
) -> OverallStatus:
    """Propagate operational and financial dimensions into overall status.

    Rules (explicit, documented):
    - OPERATIONALLY_INFEASIBLE → PLAN_INFEASIBLE (hard failure dominates)
    - NEGATIVE_CASH in any scenario → at least PLAN_AT_RISK
    - BUFFER_BREACH in any scenario → at least PLAN_AT_RISK
    - OPERATIONALLY_AT_RISK → PLAN_AT_RISK
    - OPERATIONALLY_PARTIAL + CASH_SAFE → PLAN_PARTIAL
    - OPERATIONALLY_FEASIBLE + CASH_SAFE → PLAN_FEASIBLE
    """
    if operational == OperationalStatus.OPERATIONALLY_INFEASIBLE:
        return OverallStatus.PLAN_INFEASIBLE

    if financial in {FinancialStatus.NEGATIVE_CASH, FinancialStatus.BUFFER_BREACH}:
        return OverallStatus.PLAN_AT_RISK

    if operational == OperationalStatus.OPERATIONALLY_AT_RISK:
        return OverallStatus.PLAN_AT_RISK

    if financial == FinancialStatus.CASH_AT_RISK:
        return OverallStatus.PLAN_AT_RISK

    if operational == OperationalStatus.OPERATIONALLY_PARTIAL:
        return OverallStatus.PLAN_PARTIAL

    return OverallStatus.PLAN_FEASIBLE


# ---------------------------------------------------------------------------
# Summary builders
# ---------------------------------------------------------------------------

def _build_mandatory_summary(dataset: CandidateDataset, plan: PlanResult) -> MandatorySummary:
    mandatory_items = [item for item in dataset.work_items if item.mandatory]
    selected_work_ids = set(plan.selected_actions)
    infeasible_ids = set(plan.mandatory_infeasible)
    outcomes: list[MandatoryItemOutcome] = []

    # Also include items selected as ENABLING_PREREQUISITE
    for dec in plan.decisions:
        if dec.decision == DecisionType.ENABLING_PREREQUISITE:
            selected_work_ids.add(dec.work_item_id)

    for item in mandatory_items:
        scheduled = item.id in selected_work_ids
        infeasible = item.id in infeasible_ids
        omitted = not scheduled and not infeasible
        completion = None
        prereq_ids: list[str] = []
        for dec in plan.decisions:
            if dec.work_item_id == item.id:
                cd = dec.details.get("completion_date")
                if cd:
                    from datetime import date as date_cls
                    completion = cd if isinstance(cd, date_cls) else date_cls.fromisoformat(str(cd))
                prereq_ids = dec.prerequisite_ids
        outcomes.append(MandatoryItemOutcome(
            work_item_id=item.id,
            scheduled=scheduled,
            infeasible=infeasible,
            omitted=omitted,
            prerequisite_ids=prereq_ids,
            completion_date=completion,
        ))

    return MandatorySummary(
        total_mandatory=len(mandatory_items),
        scheduled_count=sum(1 for o in outcomes if o.scheduled),
        infeasible_count=sum(1 for o in outcomes if o.infeasible),
        omitted_count=sum(1 for o in outcomes if o.omitted),
        outcomes=outcomes,
    )


def _build_capacity_summary(
    plan: PlanResult,
    violations: list[ExplanationRecord],
) -> CapacitySummary:
    people: list[PersonCapacitySummary] = []
    for usage in plan.person_capacity:
        util = (usage.used_hours / usage.capacity_hours * 100) if usage.capacity_hours > 0 else 0.0
        people.append(PersonCapacitySummary(
            person_id=usage.person_id,
            capacity_hours=usage.capacity_hours,
            used_hours=usage.used_hours,
            remaining_hours=usage.remaining_hours,
            utilisation_pct=round(min(100.0, util), 2),
        ))
    total_cap = sum(u.capacity_hours for u in plan.person_capacity)
    total_used = sum(u.used_hours for u in plan.person_capacity)
    return CapacitySummary(
        total_capacity_hours=total_cap,
        total_used_hours=round(total_used, 4),
        total_remaining_hours=round(max(0.0, total_cap - total_used), 4),
        people=people,
        violations=violations,
    )


def _build_resource_summary(
    plan: PlanResult,
    violations: list[ExplanationRecord],
) -> ResourceSummary:
    resources: list[ResourceUsageSummary] = []
    for usage in plan.resource_capacity:
        util = (usage.used_hours / usage.capacity_hours * 100) if usage.capacity_hours > 0 else 0.0
        resources.append(ResourceUsageSummary(
            resource_id=usage.resource_id,
            capacity_hours=usage.capacity_hours,
            used_hours=usage.used_hours,
            remaining_hours=usage.remaining_hours,
            exclusive=usage.exclusive,
            utilisation_pct=round(min(100.0, util), 2),
        ))
    return ResourceSummary(resources=resources, violations=violations)


def _major_risks(
    overall: OverallStatus,
    financial: FinancialStatus,
    mandatory: MandatorySummary,
) -> list[str]:
    risks: list[str] = []
    if financial == FinancialStatus.NEGATIVE_CASH:
        risks.append(ExplanationCode.NEGATIVE_CASH_EXPECTED.value)
    if financial in {FinancialStatus.BUFFER_BREACH, FinancialStatus.NEGATIVE_CASH}:
        risks.append(ExplanationCode.CASH_BUFFER_BREACH.value)
    if mandatory.infeasible_count > 0:
        risks.append(ExplanationCode.MANDATORY_WORK_INFEASIBLE.value)
    if mandatory.omitted_count > 0:
        risks.append(ExplanationCode.MANDATORY_WORK_OMITTED.value)
    if financial in {FinancialStatus.NEGATIVE_CASH, FinancialStatus.BUFFER_BREACH, FinancialStatus.CASH_AT_RISK}:
        risks.append(ExplanationCode.CASH_TIMING_MISMATCH.value)
    return risks


def _major_strengths(
    plan: PlanResult,
    mandatory: MandatorySummary,
    capacity: CapacitySummary,
) -> list[str]:
    strengths: list[str] = []
    if mandatory.scheduled_count == mandatory.total_mandatory and mandatory.infeasible_count == 0:
        strengths.append(ExplanationCode.MANDATORY_WORK_SCHEDULED.value)
    if not any(v.severity in {FindingSeverity.CRITICAL, FindingSeverity.ERROR} for v in capacity.violations):
        strengths.append(ExplanationCode.PERSON_CAPACITY_VALID.value)
    return strengths
