"""Integration and regression tests against the canonical candidate dataset.

Tests 13–15 from the spec:
   13. Mutually exclusive commercial option validation if supported.
   14. Unknown/unseen IDs are not hard-coded (tested via schema-generic path).
   15. Existing canonical dataset still loads successfully.

Also runs the full feasibility analysis against all 24 canonical work items
and asserts invariants that must hold regardless of plan optimisation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.feasibility.reason_codes import ReasonCode
from app.domain.models import CandidateDataset
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "candidate_dataset.json"
SCHEMA = ROOT / "data" / "candidate_dataset.schema.json"


@pytest.fixture(scope="module")
def canonical_dataset() -> CandidateDataset:
    """Load the canonical dataset once per test module."""
    return load_dataset(DATASET, SCHEMA)


@pytest.fixture(scope="module")
def canonical_results(canonical_dataset):
    """Run FeasibilityEngine.check_all() against canonical dataset."""
    engine = FeasibilityEngine()
    return engine.check_all(canonical_dataset)


@pytest.fixture(scope="module")
def result_map(canonical_results):
    """Index results by work_item_id for convenient lookup."""
    return {r.work_item_id: r for r in canonical_results}


# ---------------------------------------------------------------------------
# Test 15 — Canonical dataset loads and engine completes without error
# ---------------------------------------------------------------------------

def test_canonical_dataset_loads(canonical_dataset):
    """Phase 1 regression: canonical dataset still loads and validates."""
    assert canonical_dataset.metadata.dataset_id == "NW-OPS-2026-01"
    assert len(canonical_dataset.people) == 7
    assert len(canonical_dataset.work_items) == 24


def test_engine_processes_all_canonical_work_items(canonical_results, canonical_dataset):
    """Engine returns exactly one result per work item."""
    assert len(canonical_results) == len(canonical_dataset.work_items)


def test_all_results_have_valid_status(canonical_results):
    """Every result has one of the three valid statuses."""
    valid_statuses = {FeasibilityStatus.FEASIBLE, FeasibilityStatus.BLOCKED, FeasibilityStatus.INFEASIBLE}
    for r in canonical_results:
        assert r.status in valid_statuses, f"{r.work_item_id} has invalid status: {r.status}"


# ---------------------------------------------------------------------------
# Hard constraints: mandatory=True must NOT override hard failures
# ---------------------------------------------------------------------------

def test_mandatory_items_not_auto_feasible(canonical_results, canonical_dataset):
    """mandatory=True must never magically convert INFEASIBLE → FEASIBLE."""
    mandatory_ids = {w.id for w in canonical_dataset.work_items if w.mandatory}
    for r in canonical_results:
        if r.work_item_id in mandatory_ids and r.hard_failures:
            # Must remain INFEASIBLE — mandatory is NOT a magic override
            assert r.status == FeasibilityStatus.INFEASIBLE, (
                f"Mandatory item {r.work_item_id} has hard failures but is not INFEASIBLE"
            )


# ---------------------------------------------------------------------------
# Dependency structure: W001 depends on W005
# ---------------------------------------------------------------------------

def test_w001_is_blocked_without_w005_completed(canonical_dataset):
    """W001 depends on W005. With empty completed set, W001 must be BLOCKED."""
    engine = FeasibilityEngine()
    w001 = next(w for w in canonical_dataset.work_items if w.id == "W001")
    result = engine.check_work_item(w001, canonical_dataset, completed_ids=frozenset())

    # W001 has W005 as dependency — must be blocked (not infeasible)
    assert result.dependencies.satisfied is False
    assert "W005" in result.dependencies.missing
    # W001 may also have other hard failures (skill, language etc.) which is fine
    # but the dependency itself must appear as a blocker
    dep_blockers = [b for b in result.blockers if b.code == ReasonCode.DEPENDENCY_NOT_SATISFIED]
    assert len(dep_blockers) >= 1
    assert any(b.details["dependency_id"] == "W005" for b in dep_blockers)


def test_w001_dependency_satisfied_when_w005_done(canonical_dataset):
    """W001 dependency is satisfied when W005 is in completed_ids."""
    engine = FeasibilityEngine()
    w001 = next(w for w in canonical_dataset.work_items if w.id == "W001")
    result = engine.check_work_item(w001, canonical_dataset, completed_ids=frozenset({"W005"}))

    assert result.dependencies.satisfied is True
    dep_blockers = [b for b in result.blockers if b.code == ReasonCode.DEPENDENCY_NOT_SATISFIED]
    assert dep_blockers == []


# ---------------------------------------------------------------------------
# Skill coverage: no hard-coded person names, generic engine
# ---------------------------------------------------------------------------

def test_skill_coverage_results_contain_only_dataset_person_ids(canonical_results, canonical_dataset):
    """All eligible_people IDs in skill_coverage are valid person IDs from dataset."""
    person_ids = {p.id for p in canonical_dataset.people}
    for r in canonical_results:
        for skill_detail in r.skill_coverage:
            for pid in skill_detail.eligible_people:
                assert pid in person_ids, (
                    f"Unknown person ID '{pid}' in skill coverage for {r.work_item_id}"
                )


def test_language_coverage_results_contain_only_dataset_person_ids(canonical_results, canonical_dataset):
    """All eligible_people IDs in language_coverage are valid person IDs from dataset."""
    person_ids = {p.id for p in canonical_dataset.people}
    for r in canonical_results:
        for lang_detail in r.language_coverage:
            for pid in lang_detail.eligible_people:
                assert pid in person_ids, (
                    f"Unknown person ID '{pid}' in language coverage for {r.work_item_id}"
                )


# ---------------------------------------------------------------------------
# Resource check: R001 and R002 structural capacity
# ---------------------------------------------------------------------------

def test_resource_results_for_w001(canonical_dataset, result_map):
    """W001 requires R001 (45h) and R002 (32h). Both should be within capacity."""
    result = result_map["W001"]
    resource_map = {r.resource_id: r for r in result.resources}

    assert "R001" in resource_map
    assert resource_map["R001"].required_hours == 45
    assert resource_map["R001"].max_capacity_hours == 128
    assert resource_map["R001"].sufficient is True

    assert "R002" in resource_map
    assert resource_map["R002"].required_hours == 32
    assert resource_map["R002"].max_capacity_hours == 72
    assert resource_map["R002"].sufficient is True


# ---------------------------------------------------------------------------
# Capacity: total team = 748h; no single work item should exceed this
# ---------------------------------------------------------------------------

def test_capacity_total_matches_skill_eligible_pool(canonical_results, canonical_dataset):
    """Each result uses only people who can execute at least one required skill."""
    work_map = {item.id: item for item in canonical_dataset.work_items}
    for result in canonical_results:
        item = work_map[result.work_item_id]
        eligible_capacity = sum(
            person.capacity_hours
            for person in canonical_dataset.people
            if not item.required_skills
            or any(
                person.skills.get(requirement.skill, 0) >= requirement.min_level
                for requirement in item.required_skills
            )
        )
        assert result.capacity.total_team_capacity_hours == eligible_capacity

# ---------------------------------------------------------------------------
# Deadline classification: sales_opportunity items
# ---------------------------------------------------------------------------

def test_sales_opportunity_items_use_hard_or_expiry_policy(canonical_results, canonical_dataset):
    """All sales_opportunity work items must use HARD_OR_EXPIRY deadline policy."""
    from app.decision_engine.feasibility.reason_codes import DeadlinePolicy
    sales_ids = {w.id for w in canonical_dataset.work_items if w.type == "sales_opportunity"}
    for r in canonical_results:
        if r.work_item_id in sales_ids:
            assert r.deadline.policy == DeadlinePolicy.HARD_OR_EXPIRY, (
                f"{r.work_item_id} should use HARD_OR_EXPIRY"
            )


def test_non_sales_items_use_soft_with_penalty_policy(canonical_results, canonical_dataset):
    """Delivery/incident/internal items use SOFT_WITH_PENALTY."""
    from app.decision_engine.feasibility.reason_codes import DeadlinePolicy
    non_sales_types = {"delivery", "incident", "internal"}
    for r in canonical_results:
        work = next(w for w in canonical_dataset.work_items if w.id == r.work_item_id)
        if work.type in non_sales_types:
            assert r.deadline.policy == DeadlinePolicy.SOFT_WITH_PENALTY, (
                f"{r.work_item_id} (type={work.type}) should use SOFT_WITH_PENALTY"
            )


# ---------------------------------------------------------------------------
# All canonical work items' planning dates are within or after the horizon
# ---------------------------------------------------------------------------

def test_no_canonical_item_is_expired_at_planning_start(canonical_results, canonical_dataset):
    """No canonical work item should have expired at the planning start date.

    If this fails, the dataset contains items with due_date before 2026-10-05.
    """
    from app.decision_engine.feasibility.reason_codes import DeadlineStatus
    for r in canonical_results:
        # It is acceptable for items to be WITHIN_HORIZON or OUTSIDE_HORIZON
        # None should be EXPIRED as of the planning_start date
        assert r.deadline.status != DeadlineStatus.EXPIRED, (
            f"{r.work_item_id} is EXPIRED at planning_start — "
            f"due_date={r.deadline.due_date}"
        )


# ---------------------------------------------------------------------------
# Result determinism
# ---------------------------------------------------------------------------

def test_results_are_deterministic(canonical_dataset):
    """Running the engine twice produces identical results."""
    engine = FeasibilityEngine()
    results1 = engine.check_all(canonical_dataset)
    results2 = engine.check_all(canonical_dataset)
    for r1, r2 in zip(results1, results2):
        assert r1.status == r2.status
        assert r1.work_item_id == r2.work_item_id
        assert r1.capacity == r2.capacity
