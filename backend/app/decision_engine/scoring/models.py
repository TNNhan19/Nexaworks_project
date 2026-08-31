"""Immutable, traceable result models for Phase 2D scoring."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.decision_engine.assumptions import ScoringWeights

from .reason_codes import (
    ActionType,
    ComponentName,
    ReferenceSource,
    ReferenceUsage,
    ScoringReasonCode,
    ScoringSeverity,
    SelectionStatus,
)


class ReferenceDistribution(BaseModel):
    model_config = ConfigDict(frozen=True)
    values: list[float] = Field(default_factory=list)
    count: int
    minimum: float | None = None
    maximum: float | None = None


class ScoringReference(BaseModel):
    model_config = ConfigDict(frozen=True)
    reference_version: str = "2D-v1-ecdf"
    reference_source: ReferenceSource = ReferenceSource.CURRENT_SNAPSHOT
    distributions: dict[str, ReferenceDistribution] = Field(default_factory=dict)


class ScoringFinding(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: ScoringReasonCode
    severity: ScoringSeverity
    action_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ScoringComponent(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: ComponentName
    raw_value: Any = None
    normalized_value: float | None = Field(default=None, ge=0, le=1)
    applicable: bool
    configured_weight: float = Field(ge=0)
    effective_weight: float = Field(ge=0, le=1)
    weighted_contribution: float = Field(ge=0, le=1)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ScoredCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    action_id: str
    action_type: ActionType
    work_item_id: str
    option_id: str | None = None
    mandatory: bool
    selection_status: SelectionStatus
    eligible_for_selection: bool
    components: list[ScoringComponent]
    business_value_score: float | None = Field(default=None, ge=0, le=100)
    score_version: str = "2D-v1-balanced"
    reasons: list[ScoringFinding] = Field(default_factory=list)
    warnings: list[ScoringFinding] = Field(default_factory=list)

    def get_component(self, name: ComponentName | str) -> ScoringComponent | None:
        key = name.value if isinstance(name, ComponentName) else name
        return next((item for item in self.components if item.name.value == key), None)


class ScoringResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    candidates: list[ScoredCandidate]
    configured_weights: ScoringWeights
    normalization_reference: ScoringReference
    reference_usage: ReferenceUsage
    score_version: str = "2D-v1-balanced"
    reasons: list[ScoringFinding] = Field(default_factory=list)

    def get_candidate(self, action_id: str) -> ScoredCandidate | None:
        return next((item for item in self.candidates if item.action_id == action_id), None)
