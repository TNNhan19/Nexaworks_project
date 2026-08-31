"""Portfolio Effects Engine — Phase 2B public package.

Usage::

    from app.decision_engine.portfolio import PortfolioEffectsEngine, PortfolioEffectsResult
    from app.decision_engine.portfolio import PortfolioEvaluationContext

    engine = PortfolioEffectsEngine()
    context = PortfolioEffectsEngine.build_context_from_dataset(dataset)
    result = engine.evaluate(dataset, context)
"""
from .context import PortfolioEvaluationContext
from .engine import PortfolioEffectsEngine
from .models import (
    AppliedReduction,
    CashEffect,
    CommercialOptionState,
    DerivedWorkItemState,
    HoursOverride,
    PortfolioEffectEvaluation,
    PortfolioEffectsResult,
    PortfolioWarning,
    ProbabilisticHoursImpact,
)
from .reason_codes import PortfolioEffectCode, PortfolioEffectSeverity

__all__ = [
    "PortfolioEvaluationContext",
    "PortfolioEffectsEngine",
    "PortfolioEffectEvaluation",
    "PortfolioEffectsResult",
    "DerivedWorkItemState",
    "CommercialOptionState",
    "HoursOverride",
    "AppliedReduction",
    "ProbabilisticHoursImpact",
    "CashEffect",
    "PortfolioWarning",
    "PortfolioEffectCode",
    "PortfolioEffectSeverity",
]
