"""Structured result models for the Feasibility Engine.

All models are Pydantic BaseModel subclasses.  They carry machine-readable
evidence that the frontend i18n layer translates into user-facing text.

Key design decision — status hierarchy:
    INFEASIBLE  → hard_failures is non-empty
    BLOCKED     → hard_failures is empty, blockers is non-empty
    FEASIBLE    → both hard_failures and blockers are empty

Warnings may coexist with any status (e.g. mandatory item that is BLOCKED
receives a MANDATORY_ITEM_BLOCKED warning).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from .reason_codes import (
    DeadlinePolicy,
    DeadlineStatus,
    FeasibilityStatus,
    ReasonCode,
    Severity,
)


class SkillCoverageDetail(BaseModel):
    """Per-skill coverage evidence (TEAM_COVERAGE policy)."""

    skill: str
    """Skill name as it appears in the dataset."""

    required_level: float
    """Minimum level that at least one assigned person must individually meet."""

    covered: bool
    """True if at least one person individually meets or exceeds required_level."""

    eligible_people: list[str]
    """IDs of people who individually satisfy the skill threshold.
    Empty list means the skill is uncovered."""

    best_available_level: float | None
    """Highest individual level found across all people for this skill.
    None if no person has the skill listed at all."""


class LanguageCoverageDetail(BaseModel):
    """Per-language coverage evidence (CUSTOMER_FACING_COVERAGE policy)."""

    language: str
    """Language code as required by the work item."""

    covered: bool
    """True if at least one customer-facing-eligible person speaks this language."""

    eligible_people: list[str]
    """IDs of people who speak the language AND meet the customer-facing policy.
    What counts as 'customer-facing' is configured in AssumptionRegistry."""


class DependencyResult(BaseModel):
    """Dependency constraint evaluation result."""

    satisfied: bool
    """True if all required dependencies are in the completed set."""

    required: list[str]
    """All dependency work item IDs declared by this work item."""

    missing: list[str]
    """Dependencies not found in the completed_ids set.
    Missing deps yield BLOCKED status (not INFEASIBLE) because the Planner
    may schedule prerequisite work before this item."""


class CapacityResult(BaseModel):
    """Person-hour capacity check result (skill-eligible contributor policy).

    The capacity pool contains people satisfying at least one required skill.
    Work without skill requirements may use the full team.
    """

    required_hours: float
    """Total person-hours the work item needs (shared across all assignees)."""

    total_team_capacity_hours: float
    """Sum of capacity_hours across people eligible to contribute to the work."""

    sufficient: bool
    """True if total_team_capacity_hours >= required_hours."""

    note: str | None = None
    """Optional explanatory note (e.g. scope of capacity pool used)."""


class ResourceResult(BaseModel):
    """Per-shared-resource feasibility check."""

    resource_id: str
    required_hours: float
    """Hours this work item needs from the resource."""

    max_capacity_hours: float
    """Total capacity ceiling of the resource (not schedule-adjusted)."""

    sufficient: bool
    """True if required_hours <= max_capacity_hours."""

    exclusive: bool
    """True if this resource cannot be shared across simultaneous work items.
    Actual scheduling conflicts are detected by the Planner (Phase 2E)."""


class DeadlineResult(BaseModel):
    """Deadline classification result."""

    policy: DeadlinePolicy
    """Which deadline policy applies based on work item type."""

    status: DeadlineStatus
    """Relationship of due_date to the planning window."""

    due_date: date
    planning_date: date
    """The reference start date of the planning horizon."""

    planning_end: date
    days_until_due: int
    """Positive = future, zero = today, negative = already expired."""


class ReasonItem(BaseModel):
    """A single structured reason / finding from the Feasibility Engine.

    Frontend i18n maps ``code`` to a translated message template and
    fills in ``details`` for interpolation.
    """

    code: ReasonCode
    severity: Severity
    work_item_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    """Machine-readable evidence.  Content is code-specific (see reason_codes.py)."""


class FeasibilityResult(BaseModel):
    """Complete feasibility assessment for one work item.

    Status semantics:
        FEASIBLE  — no hard failures, no blockers
        BLOCKED   — no hard failures, but one or more blockers exist
        INFEASIBLE — one or more hard failures found

    Warnings may be present alongside any status.
    A mandatory item that is INFEASIBLE or BLOCKED receives an extra warning
    (MANDATORY_ITEM_INFEASIBLE / MANDATORY_ITEM_BLOCKED) so the manager is alerted.
    """

    work_item_id: str
    status: FeasibilityStatus

    # --- Detailed evidence per dimension -----------------------------------------
    skill_coverage: list[SkillCoverageDetail] = Field(default_factory=list)
    language_coverage: list[LanguageCoverageDetail] = Field(default_factory=list)
    dependencies: DependencyResult
    capacity: CapacityResult
    resources: list[ResourceResult] = Field(default_factory=list)
    deadline: DeadlineResult

    # --- Classified findings -----------------------------------------------------
    hard_failures: list[ReasonItem] = Field(default_factory=list)
    """ERROR-severity items that cause INFEASIBLE status.
    Each hard failure is a permanent constraint violation under current data."""

    blockers: list[ReasonItem] = Field(default_factory=list)
    """Items that cause BLOCKED status but are potentially resolvable by the Planner
    (e.g. scheduling prerequisite work first)."""

    warnings: list[ReasonItem] = Field(default_factory=list)
    """Non-fatal notices.  Work may still proceed; manager should be aware."""
