"""Deterministic Phase 2C Commercial Evaluation orchestrator."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any

from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.feasibility.deadline_checker import check_deadline
from app.decision_engine.feasibility.reason_codes import DeadlinePolicy, DeadlineStatus
from app.decision_engine.portfolio import PortfolioEffectsEngine, PortfolioEffectsResult
from app.domain.models import CandidateDataset, CommercialOption, LocalizedText, WorkItem

from .availability import determine_option_availability
from .deliverability import check_option_deliverability
from .metrics import (
    compute_expected_delivery_hours,
    compute_expected_follow_on_value,
    compute_expected_margin,
    compute_expected_revenue,
    compute_gross_margin,
    compute_gross_margin_ratio,
    compute_total_committed_hours,
    validate_option_fields,
)
from .models import (
    CommercialEvaluationResult,
    CommercialWarning,
    OpportunityEvaluation,
    OptionAvailabilityStatus,
    OptionDeliverabilityStatus,
    OptionMetrics,
)
from .reason_codes import CommercialReasonCode, CommercialSeverity


def _text(value: LocalizedText | str | Any, fallback: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, LocalizedText):
        return value.en or value.ja or value.vi or fallback
    if isinstance(value, dict):
        return value.get("en") or value.get("ja") or value.get("vi") or fallback
    return fallback


class CommercialEvaluationEngine:
    """Describe option facts; never score, rank, select, or schedule them."""

    def evaluate(
        self,
        dataset: CandidateDataset,
        portfolio_result: PortfolioEffectsResult,
        planning_date: date | None = None,
        completed_ids: frozenset[str] | None = None,
    ) -> CommercialEvaluationResult:
        planning_date = planning_date or dataset.metadata.planning_start
        completed_ids = completed_ids or frozenset()
        work_items = {item.id: item for item in dataset.work_items}
        option_counts = Counter(getattr(option, "option_id", None) for option in dataset.commercial_options)
        groups: dict[str, list[CommercialOption]] = defaultdict(list)
        top_warnings: list[CommercialWarning] = []

        for option in dataset.commercial_options:
            parent_id = getattr(option, "work_item_id", None)
            option_id = getattr(option, "option_id", None)
            if parent_id not in work_items:
                top_warnings.append(CommercialWarning(
                    code=CommercialReasonCode.UNKNOWN_PARENT_OPPORTUNITY,
                    severity=CommercialSeverity.ERROR,
                    option_id=option_id,
                    work_item_id=parent_id,
                    details={"work_item_id": parent_id},
                ))
                continue
            groups[parent_id].append(option)

        opportunities: list[OpportunityEvaluation] = []
        for work_item in dataset.work_items:
            if work_item.id not in groups:
                continue
            evaluation = self._evaluate_opportunity(
                work_item,
                groups[work_item.id],
                dataset,
                portfolio_result,
                planning_date,
                completed_ids,
                option_counts,
            )
            opportunities.append(evaluation)
            top_warnings.extend(evaluation.warnings)

        return CommercialEvaluationResult(opportunities=opportunities, warnings=top_warnings)

    def _evaluate_opportunity(
        self,
        work_item: WorkItem,
        options: list[CommercialOption],
        dataset: CandidateDataset,
        portfolio_result: PortfolioEffectsResult,
        planning_date: date,
        completed_ids: frozenset[str],
        option_counts: Counter,
    ) -> OpportunityEvaluation:
        deadline, _ = check_deadline(work_item, planning_date, dataset.metadata.planning_end)
        expired = deadline.policy == DeadlinePolicy.HARD_OR_EXPIRY and deadline.status == DeadlineStatus.EXPIRED
        effective_hours = portfolio_result.get_effective_hours(work_item.id, work_item.required_hours)
        base_feasibility = FeasibilityEngine().check_work_item(
            work_item,
            dataset,
            planning_date=planning_date,
            completed_ids=completed_ids,
            effective_hours_override={work_item.id: effective_hours},
        )
        blocked = base_feasibility.status == FeasibilityStatus.BLOCKED

        metrics: list[OptionMetrics] = []
        findings: list[CommercialWarning] = [CommercialWarning(
            code=CommercialReasonCode.MUTUALLY_EXCLUSIVE_OPTIONS,
            severity=CommercialSeverity.INFO,
            work_item_id=work_item.id,
            details={"option_ids": [getattr(option, "option_id", None) for option in options]},
        )]
        for option in options:
            evaluated = self._evaluate_option(
                option,
                work_item,
                dataset,
                portfolio_result,
                planning_date,
                completed_ids,
                effective_hours,
                option_counts[getattr(option, "option_id", None)] > 1,
            )
            metrics.append(evaluated)
            findings.extend(evaluated.warnings)

        return OpportunityEvaluation(
            work_item_id=work_item.id,
            title=_text(work_item.title, work_item.id),
            opportunity_expired=expired,
            opportunity_blocked=blocked,
            opportunity_due_date=work_item.due_date.isoformat(),
            options=metrics,
            warnings=findings,
        )

    def _evaluate_option(
        self,
        option: CommercialOption,
        work_item: WorkItem,
        dataset: CandidateDataset,
        portfolio_result: PortfolioEffectsResult,
        planning_date: date,
        completed_ids: frozenset[str],
        effective_base_hours: float,
        duplicate_id: bool,
    ) -> OptionMetrics:
        option_id = getattr(option, "option_id", "(missing)")
        price = getattr(option, "price_jpy", None)
        cost = getattr(option, "direct_cost_jpy", None)
        delivery = getattr(option, "delivery_hours", None)
        probability = getattr(option, "estimated_win_probability", None)
        follow_on = getattr(option, "follow_on_value_jpy", None)

        reasons = validate_option_fields(
            option_id,
            work_item.id,
            price_jpy=price,
            direct_cost_jpy=cost,
            delivery_hours=delivery,
            win_probability=probability,
            follow_on_value_jpy=follow_on,
        )
        if duplicate_id:
            reasons.append(CommercialWarning(
                code=CommercialReasonCode.DUPLICATE_COMMERCIAL_OPTION_ID,
                severity=CommercialSeverity.ERROR,
                option_id=option_id,
                work_item_id=work_item.id,
                details={"option_id": option_id},
            ))
        work_ids = {item.id for item in dataset.work_items}
        unknown_dependencies = [dep for dep in getattr(option, "dependencies", []) if dep not in work_ids]
        if unknown_dependencies:
            reasons.append(CommercialWarning(
                code=CommercialReasonCode.INVALID_COMMERCIAL_REFERENCE,
                severity=CommercialSeverity.ERROR,
                option_id=option_id,
                work_item_id=work_item.id,
                details={"unknown_dependencies": unknown_dependencies},
            ))

        invalid = any(item.severity == CommercialSeverity.ERROR for item in reasons)
        availability, availability_findings = determine_option_availability(
            option,
            work_item,
            portfolio_result,
            planning_date,
            dataset.metadata.planning_end,
            invalid=invalid,
        )
        reasons.extend(availability_findings)

        gross_margin = compute_gross_margin(price, cost)
        margin_ratio = compute_gross_margin_ratio(price, cost)
        if price == 0:
            reasons.append(CommercialWarning(
                code=CommercialReasonCode.GROSS_MARGIN_RATIO_UNDEFINED,
                severity=CommercialSeverity.INFO,
                option_id=option_id,
                work_item_id=work_item.id,
                details={"price_jpy": 0},
            ))
        total_committed = compute_total_committed_hours(work_item.required_hours, delivery)
        if availability == OptionAvailabilityStatus.INVALID:
            deliverability = OptionDeliverabilityStatus.INVALID
        elif availability == OptionAvailabilityStatus.EXPIRED:
            deliverability = OptionDeliverabilityStatus.EXPIRED
        elif availability == OptionAvailabilityStatus.LOCKED:
            deliverability = OptionDeliverabilityStatus.LOCKED
        else:
            deliverability, delivery_findings = check_option_deliverability(
                option,
                work_item,
                dataset,
                planning_date,
                completed_ids,
                effective_base_hours,
            )
            reasons.extend(delivery_findings)

        warnings = [item for item in reasons if item.severity != CommercialSeverity.INFO]
        return OptionMetrics(
            option_id=option_id,
            work_item_id=work_item.id,
            label=_text(getattr(option, "label", None), option_id),
            availability=availability,
            availability_reason_codes=[item.code for item in availability_findings],
            price_jpy=price,
            direct_cost_jpy=cost,
            gross_margin_jpy=gross_margin,
            gross_margin_ratio=margin_ratio,
            win_probability=probability,
            expected_revenue_jpy=compute_expected_revenue(price, probability),
            expected_margin_jpy=compute_expected_margin(gross_margin, probability),
            follow_on_value_jpy=follow_on,
            expected_follow_on_value_jpy=compute_expected_follow_on_value(follow_on, probability),
            base_opportunity_effort_hours=float(work_item.required_hours),
            delivery_hours=None if delivery is None else float(delivery),
            committed_delivery_hours_if_won=None if delivery is None or float(delivery) < 0 else float(delivery),
            total_committed_hours_if_won=total_committed,
            expected_delivery_hours=compute_expected_delivery_hours(delivery, probability),
            payment_days=getattr(option, "payment_days", None),
            cash_in_days=work_item.cash_in_days,
            deliverability=deliverability,
            selectable=availability == OptionAvailabilityStatus.AVAILABLE and deliverability == OptionDeliverabilityStatus.INDIVIDUALLY_DELIVERABLE,
            reasons=reasons,
            warnings=warnings,
        )

    @staticmethod
    def build_portfolio_context(
        dataset: CandidateDataset,
        completed_work_item_ids: frozenset[str] | None = None,
    ) -> PortfolioEffectsResult:
        engine = PortfolioEffectsEngine()
        context = engine.build_context_from_dataset(dataset, completed_work_item_ids or frozenset())
        return engine.evaluate(dataset, context)
