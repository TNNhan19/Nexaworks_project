"""Availability composition using Phase 2A deadlines and Phase 2B lock state."""
from __future__ import annotations

from datetime import date

from app.decision_engine.feasibility.deadline_checker import check_deadline
from app.decision_engine.feasibility.reason_codes import DeadlinePolicy, DeadlineStatus
from app.decision_engine.portfolio.models import PortfolioEffectsResult
from app.domain.models import CommercialOption, WorkItem

from .models import CommercialWarning, OptionAvailabilityStatus
from .reason_codes import CommercialReasonCode, CommercialSeverity


def determine_option_availability(
    option: CommercialOption,
    work_item: WorkItem,
    portfolio_result: PortfolioEffectsResult,
    planning_date: date,
    planning_end: date,
    invalid: bool = False,
) -> tuple[OptionAvailabilityStatus, list[CommercialWarning]]:
    """Return authoritative state; no portfolio or deadline rule is duplicated."""
    if invalid:
        return OptionAvailabilityStatus.INVALID, [CommercialWarning(
            code=CommercialReasonCode.COMMERCIAL_OPTION_INVALID,
            severity=CommercialSeverity.ERROR,
            option_id=option.option_id,
            work_item_id=work_item.id,
            details={"reason": "commercial_validation_error"},
        )]

    deadline, _ = check_deadline(work_item, planning_date, planning_end)
    if deadline.policy == DeadlinePolicy.HARD_OR_EXPIRY and deadline.status == DeadlineStatus.EXPIRED:
        return OptionAvailabilityStatus.EXPIRED, [CommercialWarning(
            code=CommercialReasonCode.COMMERCIAL_OPTION_EXPIRED,
            severity=CommercialSeverity.WARNING,
            option_id=option.option_id,
            work_item_id=work_item.id,
            details={
                "due_date": work_item.due_date.isoformat(),
                "planning_date": planning_date.isoformat(),
                "deadline_policy": deadline.policy.value,
            },
        )]

    if not portfolio_result.is_option_available(option.option_id):
        state = portfolio_result.commercial_option_states.get(option.option_id)
        details = {"portfolio_effect_lock": True}
        if state is not None:
            details.update(state.details)
            details["portfolio_reason_codes"] = [code.value for code in state.reason_codes]
        return OptionAvailabilityStatus.LOCKED, [CommercialWarning(
            code=CommercialReasonCode.COMMERCIAL_OPTION_LOCKED,
            severity=CommercialSeverity.WARNING,
            option_id=option.option_id,
            work_item_id=work_item.id,
            details=details,
        )]

    findings: list[CommercialWarning] = []
    if deadline.status == DeadlineStatus.OUTSIDE_HORIZON:
        findings.append(CommercialWarning(
            code=CommercialReasonCode.OPPORTUNITY_OUTSIDE_HORIZON,
            severity=CommercialSeverity.INFO,
            option_id=option.option_id,
            work_item_id=work_item.id,
            details={"due_date": work_item.due_date.isoformat()},
        ))
    findings.append(CommercialWarning(
        code=CommercialReasonCode.COMMERCIAL_OPTION_AVAILABLE,
        severity=CommercialSeverity.INFO,
        option_id=option.option_id,
        work_item_id=work_item.id,
        details={"portfolio_effect_lock": False},
    ))
    return OptionAvailabilityStatus.AVAILABLE, findings
