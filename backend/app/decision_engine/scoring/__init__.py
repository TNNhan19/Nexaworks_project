"""Public interface for Phase 2D Value / Priority Scoring."""
from .engine import ScoringEngine
from .models import (
    ScoredCandidate,
    ScoringComponent,
    ScoringFinding,
    ScoringReference,
    ScoringResult,
)
from .normalization import build_scoring_reference, normalize_ecdf
from .reason_codes import ActionType, ComponentName, SelectionStatus

__all__ = [
    "ScoringEngine",
    "ScoringResult",
    "ScoredCandidate",
    "ScoringComponent",
    "ScoringFinding",
    "ScoringReference",
    "build_scoring_reference",
    "normalize_ecdf",
    "ActionType",
    "ComponentName",
    "SelectionStatus",
]
