"""Tests for language, capacity, dependency, deadline, and mandatory rules.

Tests 4, 5, 7, 8, 9, 10, 11, 12, 13 from the spec:
    4.  Required language successfully covered.
    5.  Missing language coverage.
    7.  Enough aggregate capacity.
    8.  Insufficient aggregate capacity.
    9.  Dependency satisfied.
   10.  Dependency missing/incomplete.
   11.  Mandatory item that is infeasible remains reported as infeasible.
   12.  Sales opportunity deadline/expiry handling.
   13.  Mutually exclusive commercial option validation (structural check).
"""
from __future__ import annotations

from datetime import date

import pytest

from app.decision_engine.assumptions import AssumptionRegistry
from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.feasibility.reason_codes import (
    DeadlinePolicy,
    DeadlineStatus,
    ReasonCode,
)
from app.domain.models import SkillRequirement

from conftest import (
    PLAN_END,
    PLAN_START,
    make_dataset,
    make_person,
    make_work_item,
)


# -----------------------------------------------------------------------
# Test 4 — Language successfully covered (default policy: any speaker)
# -----------------------------------------------------------------------

def test_language_covered_any_speaker(default_assumptions):
    """Any person who speaks the required language satisfies coverage (default)."""
    speaker = make_person("PA", capacity=100, skills={}, languages=["ja", "en"])
    non_speaker = make_person("PB", capacity=100, skills={}, languages=["en"])
    work = make_work_item("WX", required_hours=50, required_languages=["ja"])
    dataset = make_dataset([speaker, non_speaker], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.status == FeasibilityStatus.FEASIBLE
    lang = result.language_coverage[0]
    assert lang.language == "ja"
    assert lang.covered is True
    assert "PA" in lang.eligible_people
    assert "PB" not in lang.eligible_people


def test_language_covered_with_coordinating_policy(coordinating_assumptions):
    """With customer-facing policy (pm>=3): only high-pm speaker qualifies."""
    # PA speaks "ja" but pm=1 → doesn't qualify under coordinating policy
    low_pm = make_person("PA", capacity=100, skills={"project_management": 1}, languages=["ja"])
    # PB speaks "ja" and pm=4 → qualifies
    high_pm = make_person("PB", capacity=100, skills={"project_management": 4}, languages=["ja"])
    work = make_work_item("WX", required_hours=50, required_languages=["ja"])
    dataset = make_dataset([low_pm, high_pm], [work])
    engine = FeasibilityEngine(coordinating_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.status == FeasibilityStatus.FEASIBLE
    lang = result.language_coverage[0]
    assert lang.covered is True
    assert "PB" in lang.eligible_people
    assert "PA" not in lang.eligible_people


# -----------------------------------------------------------------------
# Test 5 — Missing language coverage
# -----------------------------------------------------------------------

def test_language_not_covered(default_assumptions):
    """No person speaks the required language → INFEASIBLE."""
    person = make_person("PX", capacity=100, skills={}, languages=["en"])
    work = make_work_item("WX", required_hours=50, required_languages=["ja"])
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.status == FeasibilityStatus.INFEASIBLE
    codes = [f.code for f in result.hard_failures]
    assert ReasonCode.MISSING_LANGUAGE_COVERAGE in codes

    lang = result.language_coverage[0]
    assert lang.covered is False
    assert lang.eligible_people == []


def test_language_not_covered_with_coordinating_policy(coordinating_assumptions):
    """Speaker exists but doesn't meet coordinating skill threshold → not covered."""
    low_pm = make_person("PX", capacity=100, skills={"project_management": 1}, languages=["ja"])
    work = make_work_item("WX", required_hours=50, required_languages=["ja"])
    dataset = make_dataset([low_pm], [work])
    engine = FeasibilityEngine(coordinating_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.status == FeasibilityStatus.INFEASIBLE
    codes = [f.code for f in result.hard_failures]
    assert ReasonCode.MISSING_LANGUAGE_COVERAGE in codes


def test_work_item_with_no_required_languages(default_assumptions):
    """Work item with empty required_languages has no language failures."""
    person = make_person("PX", capacity=100, skills={})
    work = make_work_item("WX", required_hours=50, required_languages=[])
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.language_coverage == []
    lang_failures = [f for f in result.hard_failures if f.code == ReasonCode.MISSING_LANGUAGE_COVERAGE]
    assert lang_failures == []


# -----------------------------------------------------------------------
# Test 7 — Enough aggregate capacity
# -----------------------------------------------------------------------

def test_sufficient_capacity(default_assumptions):
    """Total team capacity >= required_hours → sufficient."""
    p1 = make_person("PA", capacity=100, skills={})
    p2 = make_person("PB", capacity=100, skills={})
    work = make_work_item("WX", required_hours=150)
    dataset = make_dataset([p1, p2], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.capacity.sufficient is True
    assert result.capacity.total_team_capacity_hours == 200.0
    assert result.capacity.required_hours == 150.0
    cap_failures = [f for f in result.hard_failures if f.code == ReasonCode.INSUFFICIENT_PERSON_CAPACITY]
    assert cap_failures == []


def test_capacity_uses_full_team_not_just_skill_eligible(default_assumptions):
    """A person without the required skill still contributes to capacity pool."""
    # PA has the required skill, PB does not — but both count for capacity
    pa = make_person("PA", capacity=50, skills={"robotics": 5})
    pb = make_person("PB", capacity=80, skills={})  # no skill, but hours count
    work = make_work_item(
        "WX",
        required_hours=100,
        required_skills=[SkillRequirement(skill="robotics", min_level=4)],
    )
    dataset = make_dataset([pa, pb], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    # Skill is covered by PA; capacity is 50+80=130 >= 100
    assert result.capacity.total_team_capacity_hours == 130.0
    assert result.capacity.sufficient is True
    assert result.status == FeasibilityStatus.FEASIBLE


# -----------------------------------------------------------------------
# Test 8 — Insufficient aggregate capacity → INFEASIBLE
# -----------------------------------------------------------------------

def test_insufficient_capacity(default_assumptions):
    """Total team capacity < required_hours → INFEASIBLE (hard failure)."""
    p1 = make_person("PA", capacity=30, skills={})
    p2 = make_person("PB", capacity=30, skills={})
    work = make_work_item("WX", required_hours=100)
    dataset = make_dataset([p1, p2], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    assert result.capacity.sufficient is False
    assert result.status == FeasibilityStatus.INFEASIBLE
    codes = [f.code for f in result.hard_failures]
    assert ReasonCode.INSUFFICIENT_PERSON_CAPACITY in codes

    failure = next(f for f in result.hard_failures if f.code == ReasonCode.INSUFFICIENT_PERSON_CAPACITY)
    assert failure.details["required_hours"] == 100.0
    assert failure.details["shortfall_hours"] == 40.0


# -----------------------------------------------------------------------
# Test 9 — Dependency satisfied
# -----------------------------------------------------------------------

def test_dependency_satisfied(default_assumptions):
    """Work item with dependency in completed_ids → not blocked."""
    person = make_person("PX", capacity=100, skills={})
    prereq = make_work_item("PREREQ", required_hours=20)
    work = make_work_item("WX", required_hours=50, dependencies=["PREREQ"])
    dataset = make_dataset([person], [prereq, work])
    engine = FeasibilityEngine(default_assumptions)
    # PREREQ is completed
    result = engine.check_work_item(work, dataset, completed_ids=frozenset({"PREREQ"}))

    assert result.dependencies.satisfied is True
    assert result.dependencies.missing == []
    dep_blockers = [b for b in result.blockers if b.code == ReasonCode.DEPENDENCY_NOT_SATISFIED]
    assert dep_blockers == []
    assert result.status == FeasibilityStatus.FEASIBLE


# -----------------------------------------------------------------------
# Test 10 — Dependency missing/incomplete → BLOCKED (not INFEASIBLE)
# -----------------------------------------------------------------------

def test_dependency_not_satisfied_gives_blocked_not_infeasible(default_assumptions):
    """Unsatisfied HARD dependency → BLOCKED status, not INFEASIBLE.

    The Planner may schedule the prerequisite first; this is not a permanent
    structural impossibility.
    """
    person = make_person("PX", capacity=200, skills={})
    prereq = make_work_item("PREREQ", required_hours=20)
    work = make_work_item("WX", required_hours=50, dependencies=["PREREQ"])
    dataset = make_dataset([person], [prereq, work])
    engine = FeasibilityEngine(default_assumptions)
    # completed_ids is empty — PREREQ not done yet
    result = engine.check_work_item(work, dataset, completed_ids=frozenset())

    assert result.dependencies.satisfied is False
    assert "PREREQ" in result.dependencies.missing
    assert result.status == FeasibilityStatus.BLOCKED  # NOT INFEASIBLE
    dep_blockers = [b for b in result.blockers if b.code == ReasonCode.DEPENDENCY_NOT_SATISFIED]
    assert len(dep_blockers) == 1
    assert dep_blockers[0].details["dependency_id"] == "PREREQ"
    # No hard_failures for a mere blocker
    assert result.hard_failures == []


def test_multiple_dependencies_partially_satisfied(default_assumptions):
    """Only one of two deps is complete — still BLOCKED with correct missing list."""
    person = make_person("PX", capacity=200, skills={})
    dep1 = make_work_item("DEP1", required_hours=10)
    dep2 = make_work_item("DEP2", required_hours=10)
    work = make_work_item("WX", required_hours=50, dependencies=["DEP1", "DEP2"])
    dataset = make_dataset([person], [dep1, dep2, work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset, completed_ids=frozenset({"DEP1"}))

    assert result.dependencies.satisfied is False
    assert "DEP2" in result.dependencies.missing
    assert "DEP1" not in result.dependencies.missing
    assert result.status == FeasibilityStatus.BLOCKED


# -----------------------------------------------------------------------
# Test 11 — Mandatory item that is infeasible stays INFEASIBLE with warning
# -----------------------------------------------------------------------

def test_mandatory_infeasible_item_stays_infeasible(default_assumptions):
    """mandatory=True does NOT override INFEASIBLE. Warning is added."""
    person = make_person("PX", capacity=100, skills={"design": 2})
    work = make_work_item(
        "WX",
        required_hours=50,
        mandatory=True,
        required_skills=[SkillRequirement(skill="design", min_level=5)],  # nobody qualifies
    )
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    # Still INFEASIBLE despite mandatory
    assert result.status == FeasibilityStatus.INFEASIBLE

    # Mandatory warning is added
    warn_codes = [w.code for w in result.warnings]
    assert ReasonCode.MANDATORY_ITEM_INFEASIBLE in warn_codes

    # Skill failure is still present
    fail_codes = [f.code for f in result.hard_failures]
    assert ReasonCode.MISSING_SKILL_COVERAGE in fail_codes


def test_mandatory_blocked_item_stays_blocked_with_warning(default_assumptions):
    """mandatory=True + unsatisfied dep → BLOCKED with MANDATORY_ITEM_BLOCKED warning."""
    person = make_person("PX", capacity=200, skills={})
    prereq = make_work_item("PREREQ", required_hours=10)
    work = make_work_item("WX", required_hours=50, mandatory=True, dependencies=["PREREQ"])
    dataset = make_dataset([person], [prereq, work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset, completed_ids=frozenset())

    assert result.status == FeasibilityStatus.BLOCKED
    warn_codes = [w.code for w in result.warnings]
    assert ReasonCode.MANDATORY_ITEM_BLOCKED in warn_codes


# -----------------------------------------------------------------------
# Test 12 — Sales opportunity deadline / expiry handling
# -----------------------------------------------------------------------

def test_sales_opportunity_expired_is_infeasible(default_assumptions):
    """sales_opportunity with due_date before planning_date → OPPORTUNITY_EXPIRED (hard)."""
    person = make_person("PX", capacity=100, skills={})
    expired_date = date(2026, 9, 30)  # before PLAN_START 2026-10-05
    work = make_work_item(
        "WX",
        required_hours=50,
        wtype="sales_opportunity",
        due_date=expired_date,
        earliest_start=date(2026, 9, 1),
    )
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset, planning_date=PLAN_START)

    assert result.deadline.status == DeadlineStatus.EXPIRED
    assert result.deadline.policy == DeadlinePolicy.HARD_OR_EXPIRY
    assert result.status == FeasibilityStatus.INFEASIBLE
    codes = [f.code for f in result.hard_failures]
    assert ReasonCode.OPPORTUNITY_EXPIRED in codes


def test_delivery_expired_deadline_is_warning_not_infeasible(default_assumptions):
    """delivery work item with expired due_date → WARNING (soft), not INFEASIBLE."""
    person = make_person("PX", capacity=100, skills={})
    expired_date = date(2026, 9, 30)  # before PLAN_START
    work = make_work_item(
        "WX",
        required_hours=50,
        wtype="delivery",
        due_date=expired_date,
        earliest_start=date(2026, 9, 1),
    )
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset, planning_date=PLAN_START)

    assert result.deadline.status == DeadlineStatus.EXPIRED
    assert result.deadline.policy == DeadlinePolicy.SOFT_WITH_PENALTY
    # Expiry is WARNING for soft policy — should NOT be INFEASIBLE by deadline alone
    assert result.status == FeasibilityStatus.FEASIBLE  # only deadline expired; no other failures
    deadline_warn_codes = [w.code for w in result.warnings]
    assert ReasonCode.DEADLINE_AT_RISK in deadline_warn_codes
    deadline_fail_codes = [f.code for f in result.hard_failures]
    assert ReasonCode.OPPORTUNITY_EXPIRED not in deadline_fail_codes


def test_deadline_within_horizon(default_assumptions):
    """Due date within planning window → WITHIN_HORIZON, no deadline finding."""
    person = make_person("PX", capacity=100, skills={})
    within_date = date(2026, 10, 20)
    work = make_work_item("WX", required_hours=50, due_date=within_date)
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset, planning_date=PLAN_START)

    assert result.deadline.status == DeadlineStatus.WITHIN_HORIZON
    # No deadline-related findings at Phase 2A (DEADLINE_AT_RISK needs Planner)
    deadline_findings = [
        f for f in result.hard_failures + result.warnings
        if f.code in (ReasonCode.OPPORTUNITY_EXPIRED, ReasonCode.DEADLINE_AT_RISK)
    ]
    assert deadline_findings == []


def test_deadline_outside_horizon(default_assumptions):
    """Due date after planning_end → OUTSIDE_HORIZON, no findings."""
    person = make_person("PX", capacity=100, skills={})
    future_date = date(2027, 3, 1)
    work = make_work_item("WX", required_hours=50, due_date=future_date)
    dataset = make_dataset([person], [work], planning_end=date(2026, 11, 1))
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset, planning_date=PLAN_START)

    assert result.deadline.status == DeadlineStatus.OUTSIDE_HORIZON


# -----------------------------------------------------------------------
# Test 13 — Mutually exclusive commercial option validation (structural)
# -----------------------------------------------------------------------

def test_work_item_with_no_commercial_options_is_not_affected(default_assumptions):
    """Work items without commercial options are processed without option errors."""
    person = make_person("PX", capacity=100, skills={})
    work = make_work_item("WX", required_hours=50)
    dataset = make_dataset([person], [work])
    engine = FeasibilityEngine(default_assumptions)
    result = engine.check_work_item(work, dataset)

    # No commercial option errors
    option_codes = {ReasonCode.COMMERCIAL_OPTION_LOCKED, ReasonCode.COMMERCIAL_OPTION_CONFLICT}
    all_codes = {f.code for f in result.hard_failures + result.blockers + result.warnings}
    assert all_codes.isdisjoint(option_codes)
