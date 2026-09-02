"""Structured Phase 2E planner results."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .reason_codes import AllocationType, AssignmentRole, DecisionType, PlannerReasonCode, PlanStatus


class PrerequisiteClosure(BaseModel):
    model_config = ConfigDict(frozen=True)
    target_action_id: str
    required_prerequisites: list[str] = Field(default_factory=list)
    unlock_triggers: list[str] = Field(default_factory=list)
    completion_order: list[str] = Field(default_factory=list)
    cycle_detected: bool = False
    cycle_path: list[str] = Field(default_factory=list)
    invalid_references: list[str] = Field(default_factory=list)


class PlanDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    work_item_id: str
    action_id: str
    decision: DecisionType
    selected_option_id: str | None = None
    business_value_score: float | None = None
    prerequisite_ids: list[str] = Field(default_factory=list)
    unlock_trigger_ids: list[str] = Field(default_factory=list)
    reason_codes: list[PlannerReasonCode] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class Assignment(BaseModel):
    model_config = ConfigDict(frozen=True)
    person_id: str
    action_id: str
    assigned_hours: float = Field(ge=0)
    assignment_role: AssignmentRole = AssignmentRole.CONTRIBUTOR
    skills_covered: list[str] = Field(default_factory=list)
    languages_covered: list[str] = Field(default_factory=list)


class ScheduleEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    date: date
    action_id: str
    person_id: str
    hours: float = Field(gt=0)
    allocation_type: AllocationType


class ResourceScheduleEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    date: date
    resource_id: str
    action_id: str
    hours: float = Field(gt=0)


class PersonCapacityUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    person_id: str
    capacity_hours: float
    used_hours: float
    remaining_hours: float
    available_days: int
    daily_capacity_hours: float


class ResourceCapacityUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    resource_id: str
    capacity_hours: float
    used_hours: float
    remaining_hours: float
    exclusive: bool


class PlannerWarning(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: PlannerReasonCode
    action_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PlanResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: PlanStatus
    decisions: list[PlanDecision] = Field(default_factory=list)
    prerequisite_closures: list[PrerequisiteClosure] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    schedule: list[ScheduleEntry] = Field(default_factory=list)
    resource_schedule: list[ResourceScheduleEntry] = Field(default_factory=list)
    selected_actions: list[str] = Field(default_factory=list)
    delayed_actions: list[str] = Field(default_factory=list)
    no_bid_opportunities: list[str] = Field(default_factory=list)
    mandatory_infeasible: list[str] = Field(default_factory=list)
    person_capacity: list[PersonCapacityUsage] = Field(default_factory=list)
    resource_capacity: list[ResourceCapacityUsage] = Field(default_factory=list)
    unresolved_blockers: list[PlannerWarning] = Field(default_factory=list)
    warnings: list[PlannerWarning] = Field(default_factory=list)
    planning_assumptions: dict[str, Any] = Field(default_factory=dict)
    score_version: str | None = None

    def get_decision(self, action_id: str) -> PlanDecision | None:
        return next((item for item in self.decisions if item.action_id == action_id), None)
