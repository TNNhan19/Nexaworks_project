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
    owner_id: str | None = None


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

    def _eligible_contributors(self, work_item: WorkItem) -> list[str]:
        """People may contribute only when they satisfy at least one required skill."""
        if not work_item.required_skills:
            return sorted(self.people)
        return sorted(
            person.id for person in self.dataset.people
            if any(
                person.skills.get(req.skill, 0) >= req.min_level
                for req in work_item.required_skills
            )
        )

    def _coverage_witnesses(
        self,
        work_item: WorkItem,
        dates: list[date],
        eligible_contributors: list[str],
    ) -> tuple[str | None, list[str], dict[str, list[str]], dict[str, list[str]], PlannerReasonCode | None, dict]:
        chosen: list[str] = []
        skills: dict[str, list[str]] = {}
        languages: dict[str, list[str]] = {}

        def available(person_id: str) -> bool:
            return self._available_hours(person_id, dates) > _EPS

        def skill_count(person_id: str) -> int:
            person = self.people[person_id]
            return sum(
                person.skills.get(req.skill, 0) >= req.min_level
                for req in work_item.required_skills
            )

        # The owner must be able to execute the work and cover every mandatory
        # language. Prefer the person covering the most requested skills, then
        # the one with the most available capacity, with ID as deterministic tie-break.
        owner_candidates: list[str] = []
        for person_id in eligible_contributors:
            person = self.people[person_id]
            if not all(language in person.languages for language in work_item.required_languages):
                continue
            proxy = self.assumptions.language_customer_facing_skill
            if proxy is not None and work_item.required_languages:
                if person.skills.get(proxy, 0) < self.assumptions.language_customer_facing_min_level:
                    continue
            if available(person_id):
                owner_candidates.append(person_id)

        if not owner_candidates:
            code = (
                PlannerReasonCode.MISSING_LANGUAGE_COVERAGE
                if work_item.required_languages
                else PlannerReasonCode.DELAYED_CAPACITY_LIMIT
            )
            return None, [], {}, {}, code, {
                "required_languages": work_item.required_languages,
                "eligible_contributors": eligible_contributors,
                "owner_requirement": "execution_skill_and_all_required_languages",
            }

        owner_id = sorted(
            owner_candidates,
            key=lambda pid: (-skill_count(pid), -self._available_hours(pid, dates), pid),
        )[0]
        chosen.append(owner_id)
        if work_item.required_languages:
            languages[owner_id] = list(work_item.required_languages)

        for req in work_item.required_skills:
            eligible = [
                person_id for person_id in eligible_contributors
                if self.people[person_id].skills.get(req.skill, 0) >= req.min_level
            ]
            if not eligible:
                return None, [], {}, {}, PlannerReasonCode.MISSING_SKILL_COVERAGE, {
                    "skill": req.skill,
                    "required_level": req.min_level,
                }
            candidates = [person_id for person_id in eligible if available(person_id)]
            if not candidates:
                return None, [], {}, {}, PlannerReasonCode.DELAYED_CAPACITY_LIMIT, {
                    "skill": req.skill,
                    "required_level": req.min_level,
                    "eligible_people": eligible,
                }
            witness = (
                owner_id if owner_id in candidates
                else sorted(candidates, key=lambda pid: (-self._available_hours(pid, dates), pid))[0]
            )
            skills.setdefault(witness, []).append(req.skill)
            if witness not in chosen:
                chosen.append(witness)

        return owner_id, chosen, skills, languages, None, {}

    def _allocate_person_hours(
        self,
        action_id: str,
        hours: float,
        dates: list[date],
        allocation_type: AllocationType,
        witnesses: list[str],
        eligible_people: list[str],
    ) -> list[ScheduleEntry] | None:
        if hours <= _EPS:
            return []
        if sum(self._available_hours(pid, dates) for pid in eligible_people) + _EPS < hours:
            return None
        entries: list[ScheduleEntry] = []
        remaining = hours

        # Give every coverage witness a positive allocation, then allocate the
        # remainder only among people who satisfy at least one required skill.
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
                        date=day,
                        action_id=action_id,
                        person_id=person_id,
                        hours=round(amount, 10),
                        allocation_type=allocation_type,
                    ))
                    assigned += amount
                    remaining -= amount
                    break
            if assigned <= _EPS:
                return None
            remaining_witnesses -= 1

        for day in dates:
            for person_id in eligible_people:
                if remaining <= _EPS:
                    break
                amount = min(remaining, self._remaining(person_id, day))
                if amount <= _EPS:
                    continue
                self.state.person_daily_used[person_id][day] += amount
                self.state.person_total_used[person_id] += amount
                entries.append(ScheduleEntry(
                    date=day,
                    action_id=action_id,
                    person_id=person_id,
                    hours=round(amount, 10),
                    allocation_type=allocation_type,
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

        eligible_people = self._eligible_contributors(work_item)
        witnesses: list[str] = []
        owner_id: str | None = None
        skill_map: dict[str, list[str]] = {}
        language_map: dict[str, list[str]] = {}
        if require_coverage and hours > _EPS:
            owner_id, witnesses, skill_map, language_map, failure, details = self._coverage_witnesses(
                work_item, dates, eligible_people,
            )
            if failure is not None:
                return ScheduleAttempt(False, reason_code=failure, details=details)

        entries = self._allocate_person_hours(
            action_id, hours, dates, allocation_type, witnesses, eligible_people,
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
            owner_id=owner_id,
        )
