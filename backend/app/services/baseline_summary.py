from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from app.domain.models import CandidateDataset


@dataclass(frozen=True)
class BaselineSummary:
    people_count: int
    customer_count: int
    work_item_count: int
    commercial_option_count: int
    shared_resource_count: int
    portfolio_effect_count: int
    total_people_capacity_hours: float
    total_base_work_hours: float
    mandatory_work_count: int
    mandatory_base_hours: float
    work_type_counts: dict[str, int]


def build_baseline_summary(dataset: CandidateDataset) -> BaselineSummary:
    mandatory = [w for w in dataset.work_items if w.mandatory]
    return BaselineSummary(
        people_count=len(dataset.people),
        customer_count=len(dataset.customers),
        work_item_count=len(dataset.work_items),
        commercial_option_count=len(dataset.commercial_options),
        shared_resource_count=len(dataset.shared_resources),
        portfolio_effect_count=len(dataset.portfolio_effects),
        total_people_capacity_hours=sum(p.capacity_hours for p in dataset.people),
        total_base_work_hours=sum(w.required_hours for w in dataset.work_items),
        mandatory_work_count=len(mandatory),
        mandatory_base_hours=sum(w.required_hours for w in mandatory),
        work_type_counts=dict(Counter(w.type for w in dataset.work_items)),
    )


def summary_as_dict(dataset: CandidateDataset) -> dict:
    return asdict(build_baseline_summary(dataset))
