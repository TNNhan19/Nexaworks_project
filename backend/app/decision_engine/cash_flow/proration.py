"""Exact integer-JPY conversion and deterministic proration helpers."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def exact_jpy(value: int | float | Decimal) -> int:
    """Convert a source/expected amount to nearest integer JPY deterministically."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def probability_weighted_jpy(value: int | float, probability: float) -> int:
    return exact_jpy(Decimal(str(value)) * Decimal(str(probability)))


def prorate_jpy(total_jpy: int, dates: list[date]) -> list[tuple[date, int]]:
    """Allocate an integer total exactly; earliest dates receive the remainder."""
    if total_jpy < 0:
        raise ValueError("total_jpy must be non-negative")
    if not dates:
        if total_jpy == 0:
            return []
        raise ValueError("cannot prorate a positive amount over no dates")
    ordered = sorted(dict.fromkeys(dates))
    base, remainder = divmod(total_jpy, len(ordered))
    return [
        (day, base + (1 if index < remainder else 0))
        for index, day in enumerate(ordered)
    ]
