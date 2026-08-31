from pathlib import Path

from app.services.baseline_summary import build_baseline_summary
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "candidate_dataset.json"
SCHEMA = ROOT / "data" / "candidate_dataset.schema.json"


def test_canonical_dataset_loads_and_validates() -> None:
    dataset = load_dataset(DATASET, SCHEMA)
    assert dataset.metadata.dataset_id == "NW-OPS-2026-01"
    assert len(dataset.people) == 7
    assert len(dataset.work_items) == 24


def test_baseline_numbers_match_reference_case() -> None:
    dataset = load_dataset(DATASET, SCHEMA)
    summary = build_baseline_summary(dataset)

    assert summary.total_people_capacity_hours == 748
    assert summary.total_base_work_hours == 1277
    assert summary.mandatory_work_count == 6
    assert summary.mandatory_base_hours == 433
    assert summary.commercial_option_count == 18
    assert summary.portfolio_effect_count == 5


def test_w001_skill_requirements_are_team_coverable_not_level_summable() -> None:
    dataset = load_dataset(DATASET, SCHEMA)
    w001 = next(w for w in dataset.work_items if w.id == "W001")
    requirements = {x.skill: x.min_level for x in w001.required_skills}

    assert requirements["project_management"] == 4
    assert requirements["ai"] == 4
    assert requirements["field_installation"] == 4
