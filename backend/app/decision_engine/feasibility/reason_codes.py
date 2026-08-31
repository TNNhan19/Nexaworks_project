"""Reason codes and status enumerations for the Feasibility Engine.

All values are machine-readable constants.  The frontend uses react-i18next to
translate these codes into JA / EN / VI display text — no natural-language
strings are produced inside the core engine.
"""
from __future__ import annotations

from enum import Enum


class FeasibilityStatus(str, Enum):
    """Overall feasibility verdict for a work item."""

    FEASIBLE = "FEASIBLE"
    """No hard constraints violated and no active blockers."""

    BLOCKED = "BLOCKED"
    """No permanent hard failures, but one or more blockers (e.g. unsatisfied
    HARD dependencies) prevent the work item from starting immediately.
    The Planner may resolve blockers by scheduling prerequisite work first."""

    INFEASIBLE = "INFEASIBLE"
    """One or more hard constraints cannot be satisfied under the current dataset
    and assumptions (e.g. no employee meets a required skill threshold)."""


class Severity(str, Enum):
    """Severity level attached to a ReasonItem."""

    ERROR = "ERROR"
    """Hard constraint violation — contributes to INFEASIBLE status."""

    WARNING = "WARNING"
    """Non-fatal notice — work item may still proceed but with elevated risk."""

    INFO = "INFO"
    """Informational finding — no impact on feasibility status."""


class ReasonCode(str, Enum):
    """Structured reason codes emitted by the Feasibility Engine.

    Each code is paired with a ``details`` dict containing machine-readable
    evidence.  Frontend i18n layers translate codes to display language.
    """

    MISSING_SKILL_COVERAGE = "MISSING_SKILL_COVERAGE"
    """No individual person meets the required minimum level for a skill."""

    MISSING_LANGUAGE_COVERAGE = "MISSING_LANGUAGE_COVERAGE"
    """No customer-facing person covers a required language."""

    INSUFFICIENT_PERSON_CAPACITY = "INSUFFICIENT_PERSON_CAPACITY"
    """Total team capacity is less than required_hours."""

    DEPENDENCY_NOT_SATISFIED = "DEPENDENCY_NOT_SATISFIED"
    """A HARD dependency is not in the completed set — produces a BLOCKER, not
    a permanent failure, because the Planner may schedule the prerequisite first."""

    RESOURCE_CAPACITY_EXCEEDED = "RESOURCE_CAPACITY_EXCEEDED"
    """Required resource hours exceed the resource's total capacity ceiling."""

    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    """Resource referenced by the work item does not exist in the dataset."""

    OPPORTUNITY_EXPIRED = "OPPORTUNITY_EXPIRED"
    """A sales_opportunity's due_date is before the planning_date (HARD_OR_EXPIRY
    policy) — the opportunity window has passed."""

    MANDATORY_ITEM_INFEASIBLE = "MANDATORY_ITEM_INFEASIBLE"
    """A mandatory work item is INFEASIBLE — warning so the manager is alerted."""

    MANDATORY_ITEM_BLOCKED = "MANDATORY_ITEM_BLOCKED"
    """A mandatory work item is BLOCKED — warning so the manager is alerted."""

    INVALID_WORK_REFERENCE = "INVALID_WORK_REFERENCE"
    """A required reference (e.g. dependency ID) could not be resolved."""

    COMMERCIAL_OPTION_LOCKED = "COMMERCIAL_OPTION_LOCKED"
    """A commercial option requires a portfolio-effect unlock that is not yet
    satisfied (stub — full check belongs to Phase 2B/2C)."""

    COMMERCIAL_OPTION_CONFLICT = "COMMERCIAL_OPTION_CONFLICT"
    """More than one option for the same opportunity would be selected
    (MUTUALLY_EXCLUSIVE policy violation)."""

    DEADLINE_AT_RISK = "DEADLINE_AT_RISK"
    """Due date is within the planning horizon but close — informational warning.
    Actual lateness determination requires the Planner schedule (Phase 2E)."""


class DeadlinePolicy(str, Enum):
    """Deadline treatment policy per work item type."""

    SOFT_WITH_PENALTY = "SOFT_WITH_PENALTY"
    """Delivery / internal / incident work: lateness is allowed but penalised.
    Expiry before planning_date still generates a WARNING, not INFEASIBLE."""

    HARD_OR_EXPIRY = "HARD_OR_EXPIRY"
    """Sales opportunity: expiry before planning_date makes the opportunity
    unavailable (INFEASIBLE via OPPORTUNITY_EXPIRED reason code)."""


class DeadlineStatus(str, Enum):
    """Relationship of a work item's due_date to the planning window."""

    EXPIRED = "EXPIRED"
    """due_date < planning_date — opportunity has already lapsed."""

    WITHIN_HORIZON = "WITHIN_HORIZON"
    """planning_date <= due_date <= planning_end — deadline is inside the window."""

    OUTSIDE_HORIZON = "OUTSIDE_HORIZON"
    """due_date > planning_end — deadline is after the planning window ends."""
