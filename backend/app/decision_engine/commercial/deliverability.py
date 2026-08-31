"""Individual option deliverability composed through Phase 2A."""
from __future__ import annotations

from datetime import date

from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.domain.models import CandidateDataset, CommercialOption, WorkItem

from .models import CommercialWarning, OptionDeliverabilityStatus
from .reason_codes import CommercialReasonCode, CommercialSeverity


def check_option_deliverability(
    option: CommercialOption,
    work_item: WorkItem,
    dataset: CandidateDataset,
    planning_date: date,
    completed_ids: frozenset[str],
    effective_base_hours: float,
) -> tuple[OptionDeliverabilityStatus, list[CommercialWarning]]:
    """Run Phase 2A against base + full delivery hours and merged dependencies."""
    delivery_hours = float(option.delivery_hours)  # caller validates presence/sign
    total_hours = effective_base_hours + delivery_hours
    dependencies = list(dict.fromkeys([*work_item.dependencies, *option.dependencies]))
    candidate = work_item.model_copy(update={
        "required_hours": total_hours,
        "dependencies": dependencies,
    })
    feasibility = FeasibilityEngine().check_work_item(
        candidate,
        dataset,
        planning_date=planning_date,
        completed_ids=completed_ids,
    )

    evidence = {
        "base_opportunity_effort_hours": effective_base_hours,
        "committed_delivery_hours_if_won": delivery_hours,
        "total_committed_hours_if_won": total_hours,
        "feasibility_status": feasibility.status.value,
        "option_dependencies": list(option.dependencies),
    }
    if feasibility.status == FeasibilityStatus.BLOCKED:
        evidence["blockers"] = [
            {"code": item.code.value, "details": item.details}
            for item in feasibility.blockers
        ]
        return OptionDeliverabilityStatus.BLOCKED, [CommercialWarning(
            code=CommercialReasonCode.OPTION_BLOCKED,
            severity=CommercialSeverity.WARNING,
            option_id=option.option_id,
            work_item_id=work_item.id,
            details=evidence,
        )]
    if feasibility.status == FeasibilityStatus.INFEASIBLE:
        evidence["hard_failures"] = [
            {"code": item.code.value, "details": item.details}
            for item in feasibility.hard_failures
        ]
        return OptionDeliverabilityStatus.NOT_INDIVIDUALLY_DELIVERABLE, [CommercialWarning(
            code=CommercialReasonCode.OPTION_NOT_DELIVERABLE,
            severity=CommercialSeverity.WARNING,
            option_id=option.option_id,
            work_item_id=work_item.id,
            details=evidence,
        )]
    return OptionDeliverabilityStatus.INDIVIDUALLY_DELIVERABLE, [CommercialWarning(
        code=CommercialReasonCode.OPTION_INDIVIDUALLY_DELIVERABLE,
        severity=CommercialSeverity.INFO,
        option_id=option.option_id,
        work_item_id=work_item.id,
        details=evidence,
    )]
