"""Tests for skill coverage — TEAM_COVERAGE policy.

Tests 1, 2, 3, 6, 14 from the spec:
    1. Single person covers a skill.
    2. Multiple people cover different skills.
    3. Skill levels cannot be summed.
    6. Missing skill coverage.
   14. Unknown/unseen IDs/data are not hard-coded.
"""
from __future__ import annotations

import pytest

from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.feasibility.reason_codes import ReasonCode
from app.domain.models import SkillRequirement

from conftest import (
    PLAN_END,
    PLAN_START,
    make_dataset,
    make_person,
    make_work_item,
)


# -----------------------------------------------------------------------
# Test 1 — Single person covers a skill
# -----------------------------------------------------------------------

def test_single_person_covers_skill(default_assumptions):
    """One person individually meets the threshold — skill is covered."""
    person = make_person("PX", capacity=100, skills={"engineering": 5})
    work = make_work_item(
        "WX",
        required_hours=50,
        required_skills=[SkillRequirement(skill="engineering", min_level=4)],
    )
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.status == FeasibilityStatus.FEASIBLE
    assert result.skill_coverage[0].covered is True
    assert result.skill_coverage[0].skill == "engineering"
    assert "PX" in result.skill_coverage[0].eligible_people
    assert result.hard_failures == []


# -----------------------------------------------------------------------
# Test 2 — Multiple people cover DIFFERENT skills (TEAM_COVERAGE)
# -----------------------------------------------------------------------

def test_multiple_people_cover_different_skills(default_assumptions):
    """Person A covers skill-A, Person B covers skill-B — both skills met."""
    person_a = make_person("PA", capacity=60, skills={"design": 5, "coding": 1})
    person_b = make_person("PB", capacity=60, skills={"design": 1, "coding": 5})
    work = make_work_item(
        "WX",
        required_hours=80,
        required_skills=[
            SkillRequirement(skill="design", min_level=4),
            SkillRequirement(skill="coding", min_level=4),
        ],
    )
    dataset = make_dataset([person_a, person_b], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.status == FeasibilityStatus.FEASIBLE
    skill_map = {s.skill: s for s in result.skill_coverage}
    assert skill_map["design"].covered is True
    assert "PA" in skill_map["design"].eligible_people
    assert skill_map["coding"].covered is True
    assert "PB" in skill_map["coding"].eligible_people
    assert result.hard_failures == []


# -----------------------------------------------------------------------
# Test 3 — Skill levels CANNOT be summed
# -----------------------------------------------------------------------

def test_skill_levels_cannot_be_summed(default_assumptions):
    """Two people each with AI=3 do NOT satisfy AI>=4. Levels must not be added."""
    person_a = make_person("PA", capacity=80, skills={"ai": 3})
    person_b = make_person("PB", capacity=80, skills={"ai": 3})
    work = make_work_item(
        "WX",
        required_hours=50,
        required_skills=[SkillRequirement(skill="ai", min_level=4)],
    )
    dataset = make_dataset([person_a, person_b], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    # Both have AI=3 which is below threshold 4 → INFEASIBLE
    assert result.status == FeasibilityStatus.INFEASIBLE
    skill_cov = result.skill_coverage[0]
    assert skill_cov.covered is False
    assert skill_cov.eligible_people == []
    assert skill_cov.best_available_level == 3.0

    # Hard failure should be present
    codes = [f.code for f in result.hard_failures]
    assert ReasonCode.MISSING_SKILL_COVERAGE in codes

    # Details carry evidence
    failure = next(f for f in result.hard_failures if f.code == ReasonCode.MISSING_SKILL_COVERAGE)
    assert failure.details["skill"] == "ai"
    assert failure.details["required_level"] == 4
    assert failure.details["best_available_level"] == 3.0


# -----------------------------------------------------------------------
# Test 3b — Borderline: exactly at threshold is covered
# -----------------------------------------------------------------------

def test_skill_exactly_at_threshold_is_covered(default_assumptions):
    """A skill level exactly equal to min_level satisfies the requirement."""
    person = make_person("PX", capacity=80, skills={"quality": 4})
    work = make_work_item(
        "WX",
        required_hours=40,
        required_skills=[SkillRequirement(skill="quality", min_level=4)],
    )
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.skill_coverage[0].covered is True
    assert result.status == FeasibilityStatus.FEASIBLE


# -----------------------------------------------------------------------
# Test 6 — Missing skill coverage → INFEASIBLE
# -----------------------------------------------------------------------

def test_missing_skill_coverage(default_assumptions):
    """No person has the required skill at all → INFEASIBLE."""
    person = make_person("PX", capacity=100, skills={"design": 5})
    work = make_work_item(
        "WX",
        required_hours=50,
        required_skills=[SkillRequirement(skill="robotics", min_level=3)],
    )
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.status == FeasibilityStatus.INFEASIBLE
    skill_cov = result.skill_coverage[0]
    assert skill_cov.covered is False
    assert skill_cov.best_available_level is None  # nobody has this skill

    codes = [f.code for f in result.hard_failures]
    assert ReasonCode.MISSING_SKILL_COVERAGE in codes


# -----------------------------------------------------------------------
# Test 14 — Unseen IDs / schema-conformant data is handled generically
# -----------------------------------------------------------------------

def test_unseen_skill_names_and_ids_work_generically(default_assumptions):
    """Engine works with arbitrary skill names, person IDs, and work IDs."""
    # Completely invented skill / person / work IDs not in the canonical dataset
    person = make_person(
        "NOVEL_PERSON_999",
        capacity=200,
        skills={"quantum_computing": 5, "neuroscience": 4},
    )
    work = make_work_item(
        "NOVEL_WORK_888",
        required_hours=100,
        required_skills=[
            SkillRequirement(skill="quantum_computing", min_level=4),
            SkillRequirement(skill="neuroscience", min_level=3),
        ],
    )
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.work_item_id == "NOVEL_WORK_888"
    assert result.status == FeasibilityStatus.FEASIBLE
    for detail in result.skill_coverage:
        assert detail.covered is True
        assert "NOVEL_PERSON_999" in detail.eligible_people


def test_work_item_with_no_required_skills(default_assumptions):
    """Work item with empty required_skills list should not have skill failures."""
    person = make_person("PX", capacity=100, skills={})
    work = make_work_item("WX", required_hours=50, required_skills=[])
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.skill_coverage == []
    # No skill failures
    skill_failures = [f for f in result.hard_failures if f.code == ReasonCode.MISSING_SKILL_COVERAGE]
    assert skill_failures == []
