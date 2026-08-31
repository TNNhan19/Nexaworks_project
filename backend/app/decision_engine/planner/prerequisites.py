"""Generic transitive dependency and commercial-unlock closure resolver."""
from __future__ import annotations

from app.domain.models import CandidateDataset

from .models import PrerequisiteClosure


class PrerequisiteResolver:
    def __init__(self, dataset: CandidateDataset) -> None:
        self._work = {item.id: item for item in dataset.work_items}
        self._options = {item.option_id: item for item in dataset.commercial_options}
        self._unlock: dict[str, list[str]] = {}
        for effect in dataset.portfolio_effects:
            if effect.effect.get("type") == "commercial_option_unlock":
                for target in effect.targets:
                    self._unlock.setdefault(target, []).append(effect.trigger)

    def resolve(self, action_id: str) -> PrerequisiteClosure:
        option = self._options.get(action_id)
        work_id = option.work_item_id if option is not None else action_id
        work = self._work.get(work_id)
        invalid: set[str] = set()
        unlocks = sorted(set(self._unlock.get(action_id, [])))
        roots: list[str] = []
        if work is None:
            invalid.add(work_id)
        else:
            roots.extend(work.dependencies)
        if option is not None:
            roots.extend(option.dependencies)
            roots.extend(unlocks)

        order: list[str] = []
        visiting: list[str] = []
        visited: set[str] = set()
        cycle: list[str] = []

        def visit(work_item_id: str) -> None:
            nonlocal cycle
            if cycle:
                return
            if work_item_id in visiting:
                start = visiting.index(work_item_id)
                cycle = [*visiting[start:], work_item_id]
                return
            if work_item_id in visited:
                return
            item = self._work.get(work_item_id)
            if item is None:
                invalid.add(work_item_id)
                return
            visiting.append(work_item_id)
            for dependency_id in item.dependencies:
                visit(dependency_id)
            visiting.pop()
            visited.add(work_item_id)
            order.append(work_item_id)

        for root in dict.fromkeys(roots):
            visit(root)

        return PrerequisiteClosure(
            target_action_id=action_id,
            required_prerequisites=order,
            unlock_triggers=unlocks,
            completion_order=order,
            cycle_detected=bool(cycle),
            cycle_path=cycle,
            invalid_references=sorted(invalid),
        )
