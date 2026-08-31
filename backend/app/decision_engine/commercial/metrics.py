"""Pure, Decimal-safe commercial metric calculations for Phase 2C."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .models import CommercialWarning
from .reason_codes import CommercialReasonCode, CommercialSeverity


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def validate_option_fields(
    option_id: str,
    work_item_id: str,
    *,
    price_jpy: Any,
    direct_cost_jpy: Any,
    delivery_hours: Any,
    win_probability: Any,
    follow_on_value_jpy: Any,
) -> list[CommercialWarning]:
    """Return findings without assuming absent optional values are zero."""
    warnings: list[CommercialWarning] = []
    values = {
        "price_jpy": price_jpy,
        "direct_cost_jpy": direct_cost_jpy,
        "delivery_hours": delivery_hours,
        "estimated_win_probability": win_probability,
        "follow_on_value_jpy": follow_on_value_jpy,
    }
    required = {"price_jpy", "delivery_hours", "estimated_win_probability"}

    for field, raw in values.items():
        if raw is None:
            warnings.append(CommercialWarning(
                code=CommercialReasonCode.MISSING_COMMERCIAL_FIELD,
                severity=CommercialSeverity.ERROR if field in required else CommercialSeverity.WARNING,
                option_id=option_id,
                work_item_id=work_item_id,
                details={"field": field, "required_by_schema": field in required},
            ))
        elif _decimal(raw) is None:
            warnings.append(CommercialWarning(
                code=CommercialReasonCode.MISSING_COMMERCIAL_FIELD,
                severity=CommercialSeverity.ERROR,
                option_id=option_id,
                work_item_id=work_item_id,
                details={"field": field, "value": repr(raw), "reason": "not_numeric"},
            ))

    numeric = {name: _decimal(value) for name, value in values.items()}
    probability = numeric["estimated_win_probability"]
    if probability is not None and not Decimal("0") <= probability <= Decimal("1"):
        warnings.append(CommercialWarning(
            code=CommercialReasonCode.INVALID_WIN_PROBABILITY,
            severity=CommercialSeverity.ERROR,
            option_id=option_id,
            work_item_id=work_item_id,
            details={"win_probability": float(probability), "valid_range": "[0, 1]"},
        ))

    negative_codes = {
        "price_jpy": CommercialReasonCode.NEGATIVE_PRICE,
        "direct_cost_jpy": CommercialReasonCode.NEGATIVE_COST,
        "delivery_hours": CommercialReasonCode.NEGATIVE_DELIVERY_HOURS,
        "follow_on_value_jpy": CommercialReasonCode.NEGATIVE_FOLLOW_ON_VALUE,
    }
    for field, code in negative_codes.items():
        value = numeric[field]
        if value is not None and value < 0:
            warnings.append(CommercialWarning(
                code=code,
                severity=CommercialSeverity.ERROR,
                option_id=option_id,
                work_item_id=work_item_id,
                details={field: _number(value)},
            ))

    if numeric["price_jpy"] == 0:
        warnings.append(CommercialWarning(
            code=CommercialReasonCode.ZERO_PRICE_OPTION,
            severity=CommercialSeverity.INFO,
            option_id=option_id,
            work_item_id=work_item_id,
            details={"price_jpy": 0},
        ))
    return warnings


def compute_gross_margin(price_jpy: Any, direct_cost_jpy: Any) -> int | float | None:
    price, cost = _decimal(price_jpy), _decimal(direct_cost_jpy)
    return None if price is None or cost is None else _number(price - cost)


def compute_gross_margin_ratio(price_jpy: Any, direct_cost_jpy: Any) -> float | None:
    price, cost = _decimal(price_jpy), _decimal(direct_cost_jpy)
    if price is None or cost is None or price == 0:
        return None
    return float((price - cost) / price)


def _multiply(left: Any, probability: Any) -> int | float | None:
    value, chance = _decimal(left), _decimal(probability)
    if value is None or chance is None or not Decimal("0") <= chance <= Decimal("1"):
        return None
    return _number(value * chance)


def compute_expected_revenue(price_jpy: Any, win_probability: Any) -> int | float | None:
    return _multiply(price_jpy, win_probability)


def compute_expected_margin(gross_margin_jpy: Any, win_probability: Any) -> int | float | None:
    return _multiply(gross_margin_jpy, win_probability)


def compute_expected_follow_on_value(follow_on_value_jpy: Any, win_probability: Any) -> int | float | None:
    return _multiply(follow_on_value_jpy, win_probability)


def compute_total_committed_hours(base_opportunity_hours: Any, delivery_hours: Any) -> float | None:
    base, delivery = _decimal(base_opportunity_hours), _decimal(delivery_hours)
    if base is None or delivery is None or base < 0 or delivery < 0:
        return None
    return float(base + delivery)


def compute_expected_delivery_hours(delivery_hours: Any, win_probability: Any) -> float | None:
    value = _multiply(delivery_hours, win_probability)
    return None if value is None else float(value)

