"""Reason codes and severity for Commercial Evaluation — Phase 2C.

All codes are machine-readable enums.
No localized UI strings live here.
"""
from __future__ import annotations

from enum import Enum


class CommercialSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class CommercialReasonCode(str, Enum):
    # --- Option availability ----------------------------------------------------
    COMMERCIAL_OPTION_AVAILABLE = "COMMERCIAL_OPTION_AVAILABLE"
    """Option is available for selection (no lock or expiry)."""

    COMMERCIAL_OPTION_LOCKED = "COMMERCIAL_OPTION_LOCKED"
    """Option is LOCKED by an unsatisfied portfolio-effect unlock condition."""

    COMMERCIAL_OPTION_EXPIRED = "COMMERCIAL_OPTION_EXPIRED"
    """Parent opportunity is expired (due_date < planning_date)."""

    COMMERCIAL_OPTION_INVALID = "COMMERCIAL_OPTION_INVALID"
    """Option references an unknown parent work item or has invalid data."""

    # --- Deliverability ---------------------------------------------------------
    OPTION_INDIVIDUALLY_DELIVERABLE = "OPTION_INDIVIDUALLY_DELIVERABLE"
    """This option is individually deliverable (base opportunity + delivery hours)."""

    OPTION_NOT_DELIVERABLE = "OPTION_NOT_DELIVERABLE"
    """This option is NOT individually deliverable under current team constraints."""

    OPTION_BLOCKED = "OPTION_BLOCKED"
    """Parent opportunity is BLOCKED (unsatisfied hard dependency)."""

    # --- Metrics warnings -------------------------------------------------------
    INVALID_WIN_PROBABILITY = "INVALID_WIN_PROBABILITY"
    """Win probability is outside [0, 1] range."""

    MISSING_COMMERCIAL_FIELD = "MISSING_COMMERCIAL_FIELD"
    """A required commercial field is absent or None."""

    ZERO_PRICE_OPTION = "ZERO_PRICE_OPTION"
    """Option price is zero; gross_margin_ratio is undefined."""

    NEGATIVE_PRICE = "NEGATIVE_PRICE"
    """Option price is negative — invalid dataset value."""

    NEGATIVE_COST = "NEGATIVE_COST"
    """Option direct_cost is negative — invalid dataset value."""

    NEGATIVE_DELIVERY_HOURS = "NEGATIVE_DELIVERY_HOURS"
    """Option delivery_hours is negative — invalid dataset value."""

    NEGATIVE_FOLLOW_ON_VALUE = "NEGATIVE_FOLLOW_ON_VALUE"
    """Option follow_on_value_jpy is negative — invalid dataset value."""

    GROSS_MARGIN_RATIO_UNDEFINED = "GROSS_MARGIN_RATIO_UNDEFINED"
    """Gross margin ratio cannot be calculated because price_jpy is zero."""

    # --- Integration ------------------------------------------------------------
    OPPORTUNITY_OUTSIDE_HORIZON = "OPPORTUNITY_OUTSIDE_HORIZON"
    """Opportunity due_date is beyond the planning horizon (informational)."""

    DUPLICATE_COMMERCIAL_OPTION_ID = "DUPLICATE_COMMERCIAL_OPTION_ID"
    """The option ID occurs more than once and is not safely selectable."""

    UNKNOWN_PARENT_OPPORTUNITY = "UNKNOWN_PARENT_OPPORTUNITY"
    """The option references a work item that does not exist."""

    INVALID_COMMERCIAL_REFERENCE = "INVALID_COMMERCIAL_REFERENCE"
    """A commercial option dependency/reference is unknown."""

    MUTUALLY_EXCLUSIVE_OPTIONS = "MUTUALLY_EXCLUSIVE_OPTIONS"
    """Options in one opportunity form alternatives; Phase 2C does not choose one."""
