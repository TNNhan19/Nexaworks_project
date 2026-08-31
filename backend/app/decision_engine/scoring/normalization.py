"""Deterministic reference construction and normalization helpers."""
from __future__ import annotations

from math import isfinite

from .models import ReferenceDistribution, ScoringReference


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def build_scoring_reference(raw_rows: list[dict[str, float | None]]) -> ScoringReference:
    keys = sorted({key for row in raw_rows for key in row})
    distributions: dict[str, ReferenceDistribution] = {}
    for key in keys:
        values = sorted(
            float(row[key])
            for row in raw_rows
            if row.get(key) is not None
            and isfinite(float(row[key]))
            and float(row[key]) > 0
        )
        distributions[key] = ReferenceDistribution(
            values=values,
            count=len(values),
            minimum=values[0] if values else None,
            maximum=values[-1] if values else None,
        )
    return ScoringReference(distributions=distributions)


def normalize_ecdf(raw_value: float | int | None, reference: ScoringReference, key: str) -> float | None:
    if raw_value is None:
        return None
    value = float(raw_value)
    if not isfinite(value):
        return None
    if value <= 0:
        return 0.0
    distribution = reference.distributions.get(key)
    if distribution is None or not distribution.values:
        return 1.0
    return sum(item <= value for item in distribution.values) / distribution.count


def normalize_deadline(days_until_due: int, horizon_days: int) -> float:
    if horizon_days <= 0:
        return 1.0 if days_until_due <= 0 else 0.0
    return 1.0 - clamp01(days_until_due / horizon_days)


def normalize_cash_days(days_to_cash: int | float, horizon_days: int) -> float | None:
    if days_to_cash < 0 or horizon_days <= 0:
        return None
    return 1.0 / (1.0 + float(days_to_cash) / horizon_days)
