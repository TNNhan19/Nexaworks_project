"""Deterministic day-level person and shared-resource scheduler."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable

from app.decision_engine.assumptions import AssumptionRegistry
from app.domain.models import CandidateDataset, ResourceRequirement, WorkItem

from .models import ResourceScheduleEntry, ScheduleEntry
from .reason_codes import AllocationType, PlannerReasonCode

_EPS = 1e-9


def _date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


@dataclass
class ScheduleState:
    dates: list[date]
    person_daily_capacity: dict[str, dict[date, float]]
    person_daily_used: dict[str, dict[date, float]]
    person_total_used: dict[str, float]
    resource_total_used: dict[str, float]
    resource_occupancy: dict[str, dict[date, str]]
    schedule: list[ScheduleEntry] = field(default_factory=list)
    resource_schedule: list[ResourceScheduleEntry] = field(default_factory=list)
    completion_dates: dict[str, date] = field(default_factory=dict)

    def clone(self) -> "ScheduleState":
        return deepcopy(self)


@dataclass
class ScheduleAttempt:
    success: bool
    completion_date: date | None = None
    start_date: date | None = None
    reason_code: PlannerReasonCode | None = None
    details: dict = field(default_factory=dict)
    witness_skills: dict[str, list[str]] = field(default_factory=dict)
    witness_languages: dict[str, list[str]] = field(default_factory=dict)


class DayScheduler:
    """Allocate total person-hours without inventing an eight-hour workday."""

    def __init__(self, dataset: CandidateDataset, assumptions: AssumptionRegistry) -> None:
        self.dataset = dataset
        self.assumptions = assumptions
        self.people = {person.id: person for person in dataset.people}
        self.resources = {resource.id: resource for resource in dataset.shared_resources}
        dates = _date_range(dataset.metadata.planning_start, dataset.metadata.planning_end)
        daily_capacity: dict[str, dict[date, float]] = {}
        for person in dataset.people:
            unavailable = {
                day
                for item in person.unavailable_ranges
                for day in _date_range(item.start, item.end)
            }
            available = [day for day in dates if day not in unavailable]
            per_day = person.capacity_hours / len(available) if available else 0.0
            daily_capacity[person.id] = {
                day: (0.0 if day in unavailable else per_day) for day in dates
            }
        self.state = ScheduleState(
            dates=dates,
            person_daily_capacity=daily_capacity,
            person_daily_used={pid: {day: 0.0 for day in dates} for pid in self.people},
            person_total_used={pid: 0.0 for pid in self.people},
            resource_total_used={rid: 0.0 for rid in self.resources},
            resource_occupancy={rid: {} for rid in self.resources},
        )

    def restore(self, state: ScheduleState) -> None:
        self.state = state

    def _remaining(self, person_id: str, day: date) -> float:
        return max(
            0.0,
            self.state.person_daily_capacity[person_id][day]
            - self.state.person_daily_used[person_id][day],
        )

    def _allowed_dates(
        self,
        action_id: str,
        earliest: date,
        latest: date | None,
        requirements: Iterable[ResourceRequirement],
    ) -> list[date]:
        result: list[date] = []
        for day in self.state.dates:
            if day < earliest or (latest is not None and day > latest):
                continue
            conflict = False
            for req in requirements:
                resource = self.resources.get(req.resource_id)
                if resource is None:
                    conflict = True
                    break
                if resource.exclusive and self.state.resource_occupancy[resource.id].get(day) not in (None, action_id):
                    conflict = True
                    break
            if not conflict:
                result.append(day)
        return result

    def _available_hours(self, person_id: str, dates: list[date]) -> float:
        return sum(self._remaining(person_id, day) for day in dates)

    def _coverage_witnesses(
        self,
        work_item: WorkItem,
        dates: list[date],
    ) -> tuple[list[str], dict[str, list[str]], dict[str, list[str]], PlannerReasonCode | None, dict]:
        chosen: list[str] = []
        skills: dict[str, list[str]] = {}
        languages: dict[str, list[str]] = {}

        def choose(eligible: list[str]) -> str | None:
            candidates = [pid for pid in eligible if self._available_hours(pid, dates) > _EPS]
            if not candidates:
                return None
            return sorted(candidates, key=lambda pid: (-self._available_hours(pid, dates), pid))[0]

        for req in work_item.required_skills:
            eligible = [
                person.id for person in self.dataset.people
                if person.skills.get(req.skill, 0) >= req.min_level
            ]
            if not eligible:
                return [], {}, {}, PlannerReasonCode.MISSING_SKILL_COVERAGE, {
                    "skill": req.skill, "required_level": req.min_level,
                }
            witness = choose(eligible)
            if witness is None:
                return [], {}, {}, PlannerReasonCode.DELAYED_CAPACITY_LIMIT, {
                    "skill": req.skill, "required_level": req.min_level,
                    "eligible_people": eligible,
                }
            skills.setdefault(witness, []).append(req.skill)
            if witness not in chosen:
                chosen.append(witness)

        for language in work_item.required_languages:
            eligible: list[str] = []
            for person in self.dataset.people:
                if language not in person.languages:
                    continue
                proxy = self.assumptions.language_customer_facing_skill
                if proxy is not None and person.skills.get(proxy, 0) < self.assumptions.language_customer_facing_min_level:
                    continue
                eligible.append(person.id)
            witness = choose(eligible)
            if not eligible:
                return [], {}, {}, PlannerReasonCode.MISSING_LANGUAGE_COVERAGE, {
                    "language": language,
                    "policy": self.assumptions.language_coverage_policy,
                }
            if witness is None:
                return [], {}, {}, PlannerReasonCode.DELAYED_CAPACITY_LIMIT, {
                    "language": language,
                    "policy": self.assumptions.language_coverage_policy,
                    "eligible_people": eligible,
                }
            languages.setdefault(witness, []).append(language)
            if witness not in chosen:
                chosen.append(witness)
        return chosen, skills, languages, None, {}

    def _allocate_person_hours(
        self,
        action_id: str,
        hours: float,
        dates: list[date],
        allocation_type: AllocationType,
        witnesses: list[str],
    ) -> list[ScheduleEntry] | None:
        if hours <= _EPS:
            return []
        if sum(self._available_hours(pid, dates) for pid in self.people) + _EPS < hours:
            return None
        entries: list[ScheduleEntry] = []
        remaining = hours

        # Give each coverage witness a real positive allocation on its earliest
        # available day. Coverage does not imply an invented minimum number of
        # specialist hours, so the remainder is then shared across the team.
        remaining_witnesses = len(witnesses)
        for person_id in witnesses:
            assigned = 0.0
            for day in dates:
                amount = min(
                    remaining / (remaining_witnesses + 1),
                    self._remaining(person_id, day),
                )
                if amount > _EPS:
                    self.state.person_daily_used[person_id][day] += amount
                    self.state.person_total_used[person_id] += amount
                    entries.append(ScheduleEntry(
                        date=day, action_id=action_id, person_id=person_id,
                        hours=round(amount, 10), allocation_type=allocation_type,
                    ))
                    assigned += amount
                    remaining -= amount
                    break
            if assigned <= _EPS:
                return None
            remaining_witnesses -= 1

        for day in dates:
            for person_id in sorted(self.people):
                if remaining <= _EPS:
                    break
                amount = min(remaining, self._remaining(person_id, day))
                if amount <= _EPS:
                    continue
                self.state.person_daily_used[person_id][day] += amount
                self.state.person_total_used[person_id] += amount
                entries.append(ScheduleEntry(
                    date=day, action_id=action_id, person_id=person_id,
                    hours=round(amount, 10), allocation_type=allocation_type,
                ))
                remaining -= amount
            if remaining <= _EPS:
                break
        if remaining > 1e-6:
            return None
        self.state.schedule.extend(entries)
        return entries

    def _allocate_resources(
        self,
        action_id: str,
        requirements: list[ResourceRequirement],
        active_dates: list[date],
    ) -> tuple[bool, PlannerReasonCode | None, dict]:
        for req in requirements:
            resource = self.resources.get(req.resource_id)
            if resource is None:
                return False, PlannerReasonCode.INVALID_REFERENCE, {"resource_id": req.resource_id}
            remaining = resource.capacity_hours - self.state.resource_total_used[resource.id]
            if req.hours > remaining + _EPS:
                return False, PlannerReasonCode.RESOURCE_CONFLICT, {
                    "resource_id": resource.id,
                    "required_hours": req.hours,
                    "remaining_hours": remaining,
                }
        if requirements and not active_dates:
            return False, PlannerReasonCode.RESOURCE_CONFLICT, {"reason": "no_active_schedule_day"}
        for req in requirements:
            resource = self.resources[req.resource_id]
            per_day = req.hours / len(active_dates) if active_dates else 0.0
            remaining_hours = req.hours
            for index, day in enumerate(active_dates):
                amount = remaining_hours if index == len(active_dates) - 1 else per_day
                if amount <= _EPS:
                    continue
                if resource.exclusive:
                    occupant = self.state.resource_occupancy[resource.id].get(day)
                    if occupant not in (None, action_id):
                        return False, PlannerReasonCode.RESOURCE_CONFLICT, {
                            "resource_id": resource.id, "date": day.isoformat(),
                            "conflicting_action_id": occupant,
                        }
                    self.state.resource_occupancy[resource.id][day] = action_id
                self.state.resource_schedule.append(ResourceScheduleEntry(
                    date=day, resource_id=resource.id, action_id=action_id,
                    hours=round(amount, 10),
                ))
                remaining_hours -= amount
            self.state.resource_total_used[resource.id] += req.hours
        return True, None, {}

    def schedule_phase(
        self,
        *,
        action_id: str,
        work_item: WorkItem,
        hours: float,
        earliest: date,
        latest: date | None,
        allocation_type: AllocationType,
        use_resources: bool,
        require_coverage: bool,
    ) -> ScheduleAttempt:
        checkpoint = self.state.clone()
        requirements = work_item.resource_requirements if use_resources else []
        dates = self._allowed_dates(action_id, earliest, latest, requirements)
        if hours > _EPS and not dates:
            return ScheduleAttempt(False, reason_code=PlannerReasonCode.DELAYED_CAPACITY_LIMIT)

        witnesses: list[str] = []
        skill_map: dict[str, list[str]] = {}
        language_map: dict[str, list[str]] = {}
        if require_coverage and hours > _EPS:
            witnesses, skill_map, language_map, failure, details = self._coverage_witnesses(work_item, dates)
            if failure is not None:
                return ScheduleAttempt(False, reason_code=failure, details=details)

        entries = self._allocate_person_hours(
            action_id, hours, dates, allocation_type, witnesses,
        )
        if entries is None:
            self.restore(checkpoint)
            return ScheduleAttempt(False, reason_code=PlannerReasonCode.DELAYED_CAPACITY_LIMIT)
        active_dates = sorted({entry.date for entry in entries})
        ok, failure, details = self._allocate_resources(action_id, requirements, active_dates)
        if not ok:
            self.restore(checkpoint)
            return ScheduleAttempt(False, reason_code=failure, details=details)
        return ScheduleAttempt(
            True,
            start_date=min(active_dates) if active_dates else earliest,
            completion_date=max(active_dates) if active_dates else earliest,
            witness_skills=skill_map,
            witness_languages=language_map,
        )
