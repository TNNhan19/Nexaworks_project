"""Repeated-run determinism across every decision-engine phase."""
from __future__ import annotations

from app.services.dataset_loader import validate_references

from .factories import run_pipeline


def _dump(run):
    return {
        "feasibility": [item.model_dump(mode="json") for item in run.feasibility],
        "portfolio": run.portfolio.model_dump(mode="json"),
        "commercial": run.commercial.model_dump(mode="json"),
        "scoring": run.scoring.model_dump(mode="json"),
        "plan": run.plan.model_dump(mode="json"),
        "cash": run.cash.model_dump(mode="json"),
        "final": run.final.model_dump(mode="json"),
    }


def test_every_pipeline_phase_is_identical_across_three_runs(unseen_dataset):
    first = _dump(run_pipeline(unseen_dataset))
    second = _dump(run_pipeline(unseen_dataset))
    third = _dump(run_pipeline(unseen_dataset))
    assert first == second == third


def test_reference_validation_is_deterministic(unseen_dataset):
    assert validate_references(unseen_dataset) == validate_references(unseen_dataset)
