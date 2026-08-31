"""Portfolio evaluation context — activation and scenario state.

The PortfolioEvaluationContext is the sole input to the Portfolio Effects Engine.
It carries everything needed to determine whether each effect is applicable,
without mutating any canonical data.

Design principles:
- Immutable once constructed (frozen Pydantic model).
- Deterministic: same context → same evaluation result.
- No random sampling.
- All IDs are passed in explicitly; the engine does not reach back to a global dataset.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PortfolioEvaluationContext(BaseModel):
    """Activation context for the Portfolio Effects Engine.

    Parameters
    ----------
    completed_work_item_ids:
        Work item IDs that are considered completed in this scenario.
        An effect whose trigger work item is in this set is "triggered".

    selected_work_item_ids:
        Work item IDs that have been selected/committed for execution.
        Used by downstream phases; included here for future-proofing.

    planning_date:
        Reference date for the scenario.

    all_work_item_ids:
        All work item IDs in the dataset.  Used to validate trigger/target
        references and distinguish "not completed" from "not in dataset".

    all_commercial_option_ids:
        All commercial option IDs in the dataset.  Used to validate E004-style
        option-unlock effect targets.

    notes:
        Optional freeform metadata for traceability (e.g. scenario name).
    """

    model_config = ConfigDict(frozen=True)

    completed_work_item_ids: frozenset[str] = Field(default_factory=frozenset)
    selected_work_item_ids: frozenset[str] = Field(default_factory=frozenset)
    planning_date: date | None = None
    all_work_item_ids: frozenset[str] = Field(default_factory=frozenset)
    all_commercial_option_ids: frozenset[str] = Field(default_factory=frozenset)
    notes: str | None = None

    def trigger_satisfied(self, trigger_id: str) -> bool:
        """Return True if the trigger work item is in completed_work_item_ids."""
        return trigger_id in self.completed_work_item_ids

    def work_item_exists(self, work_item_id: str) -> bool:
        """Return True if the work item ID is known in the dataset."""
        return work_item_id in self.all_work_item_ids

    def commercial_option_exists(self, option_id: str) -> bool:
        """Return True if the commercial option ID is known in the dataset."""
        return option_id in self.all_commercial_option_ids
