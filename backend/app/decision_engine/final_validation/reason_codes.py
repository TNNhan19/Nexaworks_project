"""Machine-readable enumerations for Phase 2G Final Validation + Explanation.

All values are structured codes only.  Frontend i18n layers translate them into
JA / EN / VI display text — no natural-language strings are produced here.
"""
from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Dimensional status enumerations
# ---------------------------------------------------------------------------

class OperationalStatus(str, Enum):
    """Operational / schedule validity of the plan."""

    OPERATIONALLY_FEASIBLE = "OPERATIONALLY_FEASIBLE"
    """No hard constraint violations; all mandatory items accounted for;
    no items delayed."""

    OPERATIONALLY_PARTIAL = "OPERATIONALLY_PARTIAL"
    """Plan is structurally valid but some optional items are delayed or
    some opportunities are no-bid; no hard failures."""

    OPERATIONALLY_AT_RISK = "OPERATIONALLY_AT_RISK"
    """One or more mandatory items could not be scheduled (MANDATORY_INFEASIBLE)
    or a recheck found a recoverable structural anomaly."""

    OPERATIONALLY_INFEASIBLE = "OPERATIONALLY_INFEASIBLE"
    """A hard constraint violation was detected during Phase 2G recheck that
    makes the plan structurally impossible to execute as stated."""


class FinancialStatus(str, Enum):
    """Cash-flow health of the plan across evaluated scenarios."""

    CASH_SAFE = "CASH_SAFE"
    """All evaluated scenarios remain above the minimum cash buffer."""

    CASH_AT_RISK = "CASH_AT_RISK"
    """At least one scenario breaches the buffer or would not be CASH_SAFE,
    but no scenario reaches negative cash."""

    BUFFER_BREACH = "BUFFER_BREACH"
    """At least one scenario falls below minimum_cash_buffer_jpy but
    remains non-negative."""

    NEGATIVE_CASH = "NEGATIVE_CASH"
    """At least one scenario produces negative ending cash."""


class OverallStatus(str, Enum):
    """Integrated plan status combining operational and financial dimensions."""

    PLAN_FEASIBLE = "PLAN_FEASIBLE"
    """All mandatory items handled; no hard violations; all scenarios cash-safe."""

    PLAN_PARTIAL = "PLAN_PARTIAL"
    """Operational partial (delays / no-bids) but no hard failures;
    cash is safe in all scenarios."""

    PLAN_AT_RISK = "PLAN_AT_RISK"
    """Plan has significant risk: mandatory items infeasible, or any cash
    scenario ends negative or below the buffer."""

    PLAN_INFEASIBLE = "PLAN_INFEASIBLE"
    """Hard operational constraint violation detected — plan cannot execute
    as stated without structural changes."""


# ---------------------------------------------------------------------------
# Explanation / validation finding codes
# ---------------------------------------------------------------------------

class ExplanationCode(str, Enum):
    """Structured explanation and validation finding codes for Phase 2G."""

    # --- Mandatory work -------------------------------------------------------
    MANDATORY_WORK_SCHEDULED = "MANDATORY_WORK_SCHEDULED"
    MANDATORY_WORK_INFEASIBLE = "MANDATORY_WORK_INFEASIBLE"
    MANDATORY_WORK_OMITTED = "MANDATORY_WORK_OMITTED"
    MANDATORY_PREREQUISITE_RESOLVED = "MANDATORY_PREREQUISITE_RESOLVED"

    # --- Per-decision outcomes ------------------------------------------------
    OPTION_SELECTED = "OPTION_SELECTED"
    OPTION_NOT_SELECTED = "OPTION_NOT_SELECTED"
    PLANNER_NO_BID = "PLANNER_NO_BID"
    WORK_DELAYED = "WORK_DELAYED"
    WORK_DO = "WORK_DO"
    ENABLING_PREREQUISITE = "ENABLING_PREREQUISITE"

    # --- Dependency validation ------------------------------------------------
    DEPENDENCY_ORDER_VALID = "DEPENDENCY_ORDER_VALID"
    DEPENDENCY_ORDER_VIOLATION = "DEPENDENCY_ORDER_VIOLATION"
    SELECTED_ACTION_SCHEDULE_MISSING = "SELECTED_ACTION_SCHEDULE_MISSING"

    # --- Skill / language -----------------------------------------------------
    SKILL_COVERAGE_VALID = "SKILL_COVERAGE_VALID"
    SKILL_COVERAGE_VIOLATION = "SKILL_COVERAGE_VIOLATION"
    LANGUAGE_COVERAGE_VALID = "LANGUAGE_COVERAGE_VALID"
    LANGUAGE_COVERAGE_VIOLATION = "LANGUAGE_COVERAGE_VIOLATION"

    # --- Capacity -------------------------------------------------------------
    PERSON_CAPACITY_VALID = "PERSON_CAPACITY_VALID"
    PERSON_CAPACITY_EXCEEDED = "PERSON_CAPACITY_EXCEEDED"
    DAILY_CAPACITY_EXCEEDED = "DAILY_CAPACITY_EXCEEDED"
    UNAVAILABLE_DAY_SCHEDULED = "UNAVAILABLE_DAY_SCHEDULED"

    # --- Resources ------------------------------------------------------------
    RESOURCE_CAPACITY_VALID = "RESOURCE_CAPACITY_VALID"
    RESOURCE_CAPACITY_EXCEEDED = "RESOURCE_CAPACITY_EXCEEDED"
    RESOURCE_EXCLUSIVITY_VALID = "RESOURCE_EXCLUSIVITY_VALID"
    RESOURCE_EXCLUSIVITY_VIOLATION = "RESOURCE_EXCLUSIVITY_VIOLATION"

    # --- Commercial exclusivity / unlock / expiry ----------------------------
    COMMERCIAL_EXCLUSIVITY_VALID = "COMMERCIAL_EXCLUSIVITY_VALID"
    COMMERCIAL_EXCLUSIVITY_VIOLATION = "COMMERCIAL_EXCLUSIVITY_VIOLATION"
    OPTION_LOCKED_AT_SELECTION = "OPTION_LOCKED_AT_SELECTION"
    OPTION_EXPIRED_AT_SELECTION = "OPTION_EXPIRED_AT_SELECTION"
    NO_BID_CONFLICTS_WITH_SELECTED_OPTION = "NO_BID_CONFLICTS_WITH_SELECTED_OPTION"

    # --- Schedule checks ------------------------------------------------------
    EARLIEST_START_RESPECTED = "EARLIEST_START_RESPECTED"
    EARLIEST_START_VIOLATED = "EARLIEST_START_VIOLATED"
    DEADLINE_LATE = "DEADLINE_LATE"

    # --- Cash-flow findings ---------------------------------------------------
    CASH_BUFFER_BREACH = "CASH_BUFFER_BREACH"
    NEGATIVE_CASH_EXPECTED = "NEGATIVE_CASH_EXPECTED"
    NEGATIVE_CASH_DOWNSIDE = "NEGATIVE_CASH_DOWNSIDE"
    NEGATIVE_CASH_SUCCESS = "NEGATIVE_CASH_SUCCESS"
    FUTURE_RECEIPT_OUTSIDE_HORIZON = "FUTURE_RECEIPT_OUTSIDE_HORIZON"
    CASH_TIMING_MISMATCH = "CASH_TIMING_MISMATCH"

    # --- Overall conclusions --------------------------------------------------
    PLAN_OPERATIONALLY_VALID = "PLAN_OPERATIONALLY_VALID"
    PLAN_OPERATIONALLY_PARTIAL = "PLAN_OPERATIONALLY_PARTIAL"
    PLAN_OPERATIONALLY_INFEASIBLE = "PLAN_OPERATIONALLY_INFEASIBLE"
    PLAN_FINANCIALLY_AT_RISK = "PLAN_FINANCIALLY_AT_RISK"
    PLAN_FINANCIALLY_SAFE = "PLAN_FINANCIALLY_SAFE"

    # --- Commercial option payment timing ------------------------------------
    COMMERCIAL_PAYMENT_OUTSIDE_HORIZON = "COMMERCIAL_PAYMENT_OUTSIDE_HORIZON"

    # --- Delay reasons (must match PlannerReasonCode semantics) ---------------
    DELAYED_CAPACITY_LIMIT = "DELAYED_CAPACITY_LIMIT"
    DELAYED_LOWER_PRIORITY = "DELAYED_LOWER_PRIORITY"
    DELAYED_PREREQUISITE_NOT_SELECTED = "DELAYED_PREREQUISITE_NOT_SELECTED"
    DELAYED_RESOURCE_LIMIT = "DELAYED_RESOURCE_LIMIT"
    DELAYED_HARD_CONSTRAINT = "DELAYED_HARD_CONSTRAINT"


class FindingSeverity(str, Enum):
    """Severity of a Phase 2G validation finding."""

    CRITICAL = "CRITICAL"
    """Hard failure — plan cannot execute as stated."""

    ERROR = "ERROR"
    """Significant violation requiring attention."""

    WARNING = "WARNING"
    """Elevated risk but plan may still be executed."""

    INFO = "INFO"
    """Informational finding; no impact on status."""


class SourcePhase(str, Enum):
    """Which upstream phase produced the evidence for this finding."""

    FEASIBILITY = "FEASIBILITY"
    PORTFOLIO = "PORTFOLIO"
    COMMERCIAL = "COMMERCIAL"
    SCORING = "SCORING"
    PLANNER = "PLANNER"
    CASH_FLOW = "CASH_FLOW"
    FINAL_VALIDATION = "FINAL_VALIDATION"
