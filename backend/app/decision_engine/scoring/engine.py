"""Phase 2D deterministic, explainable business-value scoring engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS, AssumptionRegistry
from app.decision_engine.commercial import (
    CommercialEvaluationResult,
    OptionAvailabilityStatus,
    OptionDeliverabilityStatus,
    OptionMetrics,
)
from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityResult, FeasibilityStatus
from app.decision_engine.portfolio import PortfolioEffectCode, PortfolioEffectsResult
from app.domain.models import CandidateDataset, WorkItem

from .models import (
    ScoredCandidate,
    ScoringComponent,
    ScoringFinding,
    ScoringReference,
    ScoringResult,
)
from .normalization import (
    build_scoring_reference,
    normalize_cash_days,
    normalize_deadline,
    normalize_ecdf,
)
from .reason_codes import (
    ActionType,
    ComponentName,
    ReferenceUsage,
    ScoringReasonCode,
    ScoringSeverity,
    SelectionStatus,
)

_REFERENCE_KEYS = {
    ComponentName.ECONOMIC_VALUE: "economic_value",
    ComponentName.STRATEGIC_CUSTOMER: "strategic_customer",
    ComponentName.FOLLOW_ON_VALUE: "follow_on_value",
    ComponentName.CAPACITY_EFFICIENCY: "capacity_efficiency",
}


@dataclass
class _RawCandidate:
    action_id: str
    action_type: ActionType
    work_item: WorkItem
    option: OptionMetrics | None
    status: SelectionStatus
    economic: int | float | None
    strategic: float | None
    days_until_due: int
    late_penalty: int | float
    cash_days: int | None
    follow_on: int | float | None
    committed_hours: float | None
    capacity_efficiency: float | None
    risk_resilience: float | None
    risk_codes: list[str] = field(default_factory=list)
    source_status: dict[str, Any] = field(default_factory=dict)

    def reference_values(self) -> dict[str, float | None]:
        return {
            "economic_value": None if self.economic is None else float(self.economic),
            "strategic_customer": self.strategic,
            "late_penalty_jpy_per_day": float(self.late_penalty),
            "follow_on_value": None if self.follow_on is None else float(self.follow_on),
            "capacity_efficiency": self.capacity_efficiency,
        }


def _money_expected_margin(work_item: WorkItem) -> int | float:
    value = (
        (Decimal(str(work_item.revenue_jpy)) - Decimal(str(work_item.direct_cost_jpy)))
        * Decimal(str(work_item.success_probability))
    )
    return int(value) if value == value.to_integral_value() else float(value)


class ScoringEngine:
    """Score business value separately from operational eligibility."""

    def __init__(self, assumptions: AssumptionRegistry = DEFAULT_ASSUMPTIONS) -> None:
        self._assumptions = assumptions

    def evaluate(
        self,
        dataset: CandidateDataset,
        portfolio_result: PortfolioEffectsResult,
        commercial_result: CommercialEvaluationResult,
        *,
        feasibility_results: list[FeasibilityResult] | None = None,
        scoring_reference: ScoringReference | None = None,
        planning_date: date | None = None,
        completed_ids: frozenset[str] | None = None,
    ) -> ScoringResult:
        planning_date = planning_date or dataset.metadata.planning_start
        completed_ids = completed_ids or frozenset()
        effective_hours = {
            item.id: portfolio_result.get_effective_hours(item.id, item.required_hours)
            for item in dataset.work_items
        }
        if feasibility_results is None:
            feasibility_results = FeasibilityEngine(self._assumptions).check_all(
                dataset,
                planning_date=planning_date,
                completed_ids=completed_ids,
                effective_hours_override=effective_hours,
            )
        feasibility_by_id = {item.work_item_id: item for item in feasibility_results}
        commercial_by_work = {
            item.work_item_id: item for item in commercial_result.opportunities
        }

        raw_candidates: list[_RawCandidate] = []
        for work_item in dataset.work_items:
            opportunity = commercial_by_work.get(work_item.id)
            if opportunity is not None:
                for option in opportunity.options:
                    raw_candidates.append(self._raw_option(
                        work_item,
                        option,
                        portfolio_result,
                        planning_date,
                    ))
            else:
                raw_candidates.append(self._raw_work_item(
                    work_item,
                    feasibility_by_id[work_item.id],
                    portfolio_result,
                    planning_date,
                    effective_hours[work_item.id],
                ))

        if scoring_reference is None:
            reference = build_scoring_reference(
                [candidate.reference_values() for candidate in raw_candidates]
            )
            reference_usage = ReferenceUsage.BUILT
            reference_code = ScoringReasonCode.NORMALIZATION_REFERENCE_BUILT
        else:
            reference = scoring_reference
            reference_usage = ReferenceUsage.REUSED
            reference_code = ScoringReasonCode.NORMALIZATION_REFERENCE_REUSED

        candidates = [
            self._score_candidate(raw, reference, dataset)
            for raw in raw_candidates
        ]
        return ScoringResult(
            candidates=candidates,
            configured_weights=self._assumptions.scoring_weights,
            normalization_reference=reference,
            reference_usage=reference_usage,
            reasons=[ScoringFinding(
                code=reference_code,
                severity=ScoringSeverity.INFO,
                details={
                    "reference_source": reference.reference_source.value,
                    "reference_version": reference.reference_version,
                    "distribution_counts": {
                        key: distribution.count
                        for key, distribution in reference.distributions.items()
                    },
                },
            )],
        )

    def _raw_work_item(
        self,
        work_item: WorkItem,
        feasibility: FeasibilityResult,
        portfolio_result: PortfolioEffectsResult,
        planning_date: date,
        effective_hours: float,
    ) -> _RawCandidate:
        economic = _money_expected_margin(work_item)
        capacity_efficiency = (
            float(economic) / effective_hours if effective_hours > 0 else None
        )
        cash_days = (
            work_item.cash_in_days
            if work_item.revenue_jpy > 0 and work_item.cash_in_days is not None
            else None
        )
        risk_value, risk_codes = self._risk_state(work_item.id, portfolio_result)
        status = {
            FeasibilityStatus.FEASIBLE: SelectionStatus.ELIGIBLE,
            FeasibilityStatus.BLOCKED: SelectionStatus.BLOCKED,
            FeasibilityStatus.INFEASIBLE: SelectionStatus.INFEASIBLE,
        }[feasibility.status]
        return _RawCandidate(
            action_id=work_item.id,
            action_type=ActionType.DO_WORK_ITEM,
            work_item=work_item,
            option=None,
            status=status,
            economic=economic,
            strategic=work_item.strategic_value,
            days_until_due=(work_item.due_date - planning_date).days,
            late_penalty=work_item.late_penalty_jpy_per_day,
            cash_days=cash_days,
            follow_on=None,
            committed_hours=effective_hours,
            capacity_efficiency=capacity_efficiency,
            risk_resilience=risk_value,
            risk_codes=risk_codes,
            source_status={
                "feasibility_status": feasibility.status.value,
                "hard_failure_codes": [item.code.value for item in feasibility.hard_failures],
                "blocker_codes": [item.code.value for item in feasibility.blockers],
            },
        )

    def _raw_option(
        self,
        work_item: WorkItem,
        option: OptionMetrics,
        portfolio_result: PortfolioEffectsResult,
        planning_date: date,
    ) -> _RawCandidate:
        status = self._option_status(option)
        hours = option.total_committed_hours_if_won
        capacity_efficiency = (
            float(option.expected_margin_jpy) / hours
            if option.expected_margin_jpy is not None and hours is not None and hours > 0
            else None
        )
        cash_days = (
            option.payment_days
            if option.price_jpy is not None and option.price_jpy > 0 and option.payment_days is not None
            else None
        )
        risk_value, risk_codes = self._risk_state(work_item.id, portfolio_result)
        return _RawCandidate(
            action_id=option.option_id,
            action_type=ActionType.SELECT_OPTION,
            work_item=work_item,
            option=option,
            status=status,
            economic=option.expected_margin_jpy,
            strategic=work_item.strategic_value,
            days_until_due=(work_item.due_date - planning_date).days,
            late_penalty=work_item.late_penalty_jpy_per_day,
            cash_days=cash_days,
            follow_on=option.expected_follow_on_value_jpy,
            committed_hours=hours,
            capacity_efficiency=capacity_efficiency,
            risk_resilience=risk_value,
            risk_codes=risk_codes,
            source_status={
                "availability": option.availability.value,
                "deliverability": option.deliverability.value,
                "commercial_selectable": option.selectable,
            },
        )

    @staticmethod
    def _option_status(option: OptionMetrics) -> SelectionStatus:
        availability_map = {
            OptionAvailabilityStatus.LOCKED: SelectionStatus.LOCKED,
            OptionAvailabilityStatus.EXPIRED: SelectionStatus.EXPIRED,
            OptionAvailabilityStatus.INVALID: SelectionStatus.INVALID,
        }
        if option.availability in availability_map:
            return availability_map[option.availability]
        deliverability_map = {
            OptionDeliverabilityStatus.BLOCKED: SelectionStatus.BLOCKED,
            OptionDeliverabilityStatus.LOCKED: SelectionStatus.LOCKED,
            OptionDeliverabilityStatus.EXPIRED: SelectionStatus.EXPIRED,
            OptionDeliverabilityStatus.INVALID: SelectionStatus.INVALID,
            OptionDeliverabilityStatus.NOT_INDIVIDUALLY_DELIVERABLE: SelectionStatus.INFEASIBLE,
            OptionDeliverabilityStatus.INDIVIDUALLY_DELIVERABLE: SelectionStatus.ELIGIBLE,
        }
        return deliverability_map[option.deliverability]

    def _risk_state(
        self,
        work_item_id: str,
        portfolio_result: PortfolioEffectsResult,
    ) -> tuple[float | None, list[str]]:
        codes = [
            warning.code
            for warning in portfolio_result.warnings
            if warning.target_id == work_item_id
            and warning.code in {
                PortfolioEffectCode.QUALITY_PREREQUISITE_RISK,
                PortfolioEffectCode.QUALITY_PREREQUISITE_SATISFIED,
            }
        ]
        if PortfolioEffectCode.QUALITY_PREREQUISITE_RISK in codes:
            return self._assumptions.scoring_quality_risk_resilience, [code.value for code in codes]
        if PortfolioEffectCode.QUALITY_PREREQUISITE_SATISFIED in codes:
            return 1.0, [code.value for code in codes]
        return None, []

    def _score_candidate(
        self,
        raw: _RawCandidate,
        reference: ScoringReference,
        dataset: CandidateDataset,
    ) -> ScoredCandidate:
        horizon_days = (dataset.metadata.planning_end - dataset.metadata.planning_start).days
        weights = self._assumptions.scoring_weights.model_dump()
        deadline_value = normalize_deadline(raw.days_until_due, horizon_days)
        penalty_value = normalize_ecdf(raw.late_penalty, reference, "late_penalty_jpy_per_day") or 0.0
        urgency_value = (deadline_value + penalty_value) / 2.0
        cash_value = (
            normalize_cash_days(raw.cash_days, horizon_days)
            if raw.cash_days is not None
            else None
        )
        normalized = {
            ComponentName.ECONOMIC_VALUE: normalize_ecdf(raw.economic, reference, "economic_value"),
            ComponentName.STRATEGIC_CUSTOMER: normalize_ecdf(raw.strategic, reference, "strategic_customer"),
            ComponentName.URGENCY_COST_OF_DELAY: urgency_value,
            ComponentName.CASH_TIMING: cash_value,
            ComponentName.FOLLOW_ON_VALUE: normalize_ecdf(raw.follow_on, reference, "follow_on_value"),
            ComponentName.CAPACITY_EFFICIENCY: normalize_ecdf(raw.capacity_efficiency, reference, "capacity_efficiency"),
            ComponentName.RISK_RESILIENCE: raw.risk_resilience,
        }
        raw_values: dict[ComponentName, Any] = {
            ComponentName.ECONOMIC_VALUE: raw.economic,
            ComponentName.STRATEGIC_CUSTOMER: raw.strategic,
            ComponentName.URGENCY_COST_OF_DELAY: {
                "days_until_due": raw.days_until_due,
                "late_penalty_jpy_per_day": raw.late_penalty,
            },
            ComponentName.CASH_TIMING: raw.cash_days,
            ComponentName.FOLLOW_ON_VALUE: raw.follow_on,
            ComponentName.CAPACITY_EFFICIENCY: raw.capacity_efficiency,
            ComponentName.RISK_RESILIENCE: raw.risk_resilience,
        }
        applicable_total = sum(
            weights[name.value] for name, value in normalized.items() if value is not None
        )
        reasons = [self._status_finding(raw)]
        warnings: list[ScoringFinding] = []
        components: list[ScoringComponent] = []

        for name in ComponentName:
            value = normalized[name]
            configured = weights[name.value]
            applicable = value is not None
            effective = configured / applicable_total if applicable and applicable_total > 0 else 0.0
            contribution = (value or 0.0) * effective
            if not applicable:
                reasons.append(ScoringFinding(
                    code=ScoringReasonCode.COMPONENT_NOT_APPLICABLE,
                    severity=ScoringSeverity.INFO,
                    action_id=raw.action_id,
                    details={"component": name.value},
                ))
            components.append(ScoringComponent(
                name=name,
                raw_value=raw_values[name],
                normalized_value=value,
                applicable=applicable,
                configured_weight=configured,
                effective_weight=effective,
                weighted_contribution=contribution,
                evidence=self._component_evidence(name, raw, reference, deadline_value, penalty_value, horizon_days),
            ))

        if abs(applicable_total - 1.0) > 1e-12:
            reasons.append(ScoringFinding(
                code=ScoringReasonCode.COMPONENT_WEIGHTS_RENORMALIZED,
                severity=ScoringSeverity.INFO,
                action_id=raw.action_id,
                details={"applicable_configured_weight_sum": applicable_total},
            ))
        if raw.economic is not None and raw.economic < 0:
            warnings.append(ScoringFinding(
                code=ScoringReasonCode.NEGATIVE_ECONOMIC_VALUE,
                severity=ScoringSeverity.WARNING,
                action_id=raw.action_id,
                details={"economic_value": raw.economic},
            ))
        if raw.risk_codes and raw.risk_resilience is not None and raw.risk_resilience < 1:
            warnings.append(ScoringFinding(
                code=ScoringReasonCode.PORTFOLIO_RISK_PRESENT,
                severity=ScoringSeverity.WARNING,
                action_id=raw.action_id,
                details={"portfolio_codes": raw.risk_codes, "resilience_value": raw.risk_resilience},
            ))
        score = round(100.0 * sum(item.weighted_contribution for item in components), 2)
        return ScoredCandidate(
            action_id=raw.action_id,
            action_type=raw.action_type,
            work_item_id=raw.work_item.id,
            option_id=raw.option.option_id if raw.option is not None else None,
            mandatory=raw.work_item.mandatory,
            selection_status=raw.status,
            eligible_for_selection=raw.status == SelectionStatus.ELIGIBLE,
            components=components,
            business_value_score=score,
            reasons=reasons,
            warnings=warnings,
        )

    @staticmethod
    def _status_finding(raw: _RawCandidate) -> ScoringFinding:
        codes = {
            SelectionStatus.ELIGIBLE: ScoringReasonCode.SCORING_ELIGIBLE,
            SelectionStatus.BLOCKED: ScoringReasonCode.SCORING_BLOCKED,
            SelectionStatus.LOCKED: ScoringReasonCode.SCORING_LOCKED,
            SelectionStatus.EXPIRED: ScoringReasonCode.SCORING_EXPIRED,
            SelectionStatus.INFEASIBLE: ScoringReasonCode.SCORING_INFEASIBLE,
            SelectionStatus.INVALID: ScoringReasonCode.SCORING_INVALID,
        }
        severity = ScoringSeverity.INFO if raw.status == SelectionStatus.ELIGIBLE else ScoringSeverity.WARNING
        return ScoringFinding(
            code=codes[raw.status],
            severity=severity,
            action_id=raw.action_id,
            details=raw.source_status,
        )

    @staticmethod
    def _component_evidence(
        name: ComponentName,
        raw: _RawCandidate,
        reference: ScoringReference,
        deadline_value: float,
        penalty_value: float,
        horizon_days: int,
    ) -> dict[str, Any]:
        if name == ComponentName.ECONOMIC_VALUE:
            return {
                "source": "phase_2c_expected_margin_jpy" if raw.option else "work_item_expected_margin_jpy",
                "normalization": "positive_empirical_cdf",
            }
        if name == ComponentName.STRATEGIC_CUSTOMER:
            return {"source": "work_item.strategic_value", "normalization": "positive_empirical_cdf"}
        if name == ComponentName.URGENCY_COST_OF_DELAY:
            return {
                "formula": "0.5*deadline_proximity+0.5*late_penalty_percentile",
                "deadline_proximity": deadline_value,
                "late_penalty_percentile": penalty_value,
                "horizon_days": horizon_days,
            }
        if name == ComponentName.CASH_TIMING:
            return {"formula": "1/(1+days_to_cash/horizon_days)", "horizon_days": horizon_days}
        if name == ComponentName.FOLLOW_ON_VALUE:
            return {"source": "phase_2c_expected_follow_on_value_jpy", "normalization": "positive_empirical_cdf"}
        if name == ComponentName.CAPACITY_EFFICIENCY:
            return {
                "formula": "economic_value/committed_hours",
                "committed_hours": raw.committed_hours,
                "hours_source": "phase_2c_total_committed_hours_if_won" if raw.option else "phase_2b_effective_required_hours",
                "normalization": "positive_empirical_cdf",
            }
        return {
            "source": "phase_2b_quality_prerequisite",
            "portfolio_codes": raw.risk_codes,
        }
