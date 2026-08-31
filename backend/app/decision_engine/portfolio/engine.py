"""Portfolio Effects Engine — Phase 2B orchestrator.

Answers: "Given the current scenario context, which portfolio effects are
applicable, what do they change, what risks/warnings do they create, and
what uncertainty must downstream modules know about?"

Critical design rules:
    - The canonical CandidateDataset is NEVER mutated.
    - All derived state is returned in PortfolioEffectsResult.
    - Evaluation is deterministic: same context → same result.
    - No random sampling.
    - All effects are idempotent: running twice on the same context produces
      identical results (always derives from canonical base values).

Pipeline:
    1. Build index maps from the dataset.
    2. Iterate declared portfolio_effects in order.
    3. Dispatch each effect to the appropriate handler based on effect.type.
    4. Aggregate results into PortfolioEffectsResult.
    5. Build derived work item states and option availability indexes.

The engine is:
    - Framework-independent (no FastAPI imports).
    - Free of hard-coded effect IDs or work item IDs.
"""
from __future__ import annotations

from app.domain.models import CandidateDataset, PortfolioEffect

from .context import PortfolioEvaluationContext
from .handlers.cash_inflow import handle_cash_inflow
from .handlers.commercial_option_unlock import handle_commercial_option_unlock
from .handlers.future_hours_reduction import handle_future_hours_reduction
from .handlers.hours_reduction import handle_hours_reduction
from .handlers.quality_prerequisite import handle_quality_prerequisite
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

# Registered effect types → handler dispatch
_SUPPORTED_TYPES = {
    "quality_prerequisite",
    "hours_reduction",
    "future_hours_reduction",
    "commercial_option_unlock",
    "cash_inflow",
}


class PortfolioEffectsEngine:
    """Phase 2B Portfolio Effects Engine.

    Evaluates all declared portfolio effects against a given context and
    returns a PortfolioEffectsResult consumed by downstream phases.

    Usage::

        engine = PortfolioEffectsEngine()
        context = PortfolioEvaluationContext(
            completed_work_item_ids=frozenset({"W013"}),
            all_work_item_ids=frozenset(w.id for w in dataset.work_items),
            all_commercial_option_ids=frozenset(o.option_id for o in dataset.commercial_options),
        )
        result = engine.evaluate(dataset, context)
        effective_hours = result.get_effective_hours("W015", base_hours=68.0)

    The engine never modifies the dataset or context; it is pure and deterministic.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        dataset: CandidateDataset,
        context: PortfolioEvaluationContext,
    ) -> PortfolioEffectsResult:
        """Evaluate all portfolio effects in the dataset.

        Parameters
        ----------
        dataset:
            Validated CandidateDataset.  Not mutated.
        context:
            Activation context specifying which work items are completed.

        Returns
        -------
        PortfolioEffectsResult with all effect evaluations and derived indexes.
        """
        # --- Index maps built once from canonical data -----------------------
        base_hours_map: dict[str, float] = {
            w.id: w.required_hours for w in dataset.work_items
        }

        all_evaluations: list[PortfolioEffectEvaluation] = []
        # pending_overrides: per-effect HoursOverride records, keyed by target_id
        # Multiple entries for the same target_id indicate a collision.
        pending_overrides: dict[str, list[HoursOverride]] = {}
        all_prob_impacts: dict[str, ProbabilisticHoursImpact] = {}
        all_option_states: dict[str, CommercialOptionState] = {}
        all_cash_effects: list[CashEffect] = []
        all_warnings: list[PortfolioWarning] = []

        # --- Dispatch each declared effect -----------------------------------
        for effect in dataset.portfolio_effects:
            evaluation, effect_warnings, new_overrides = self._dispatch(
                effect=effect,
                context=context,
                base_hours_map=base_hours_map,
                prob_impacts=all_prob_impacts,
                option_states_map=all_option_states,
                cash_effects=all_cash_effects,
            )
            all_evaluations.append(evaluation)
            all_warnings.extend(effect_warnings)
            # Accumulate per-effect overrides by target (preserving all for compounding)
            for wid, override in new_overrides.items():
                pending_overrides.setdefault(wid, []).append(override)

        # --- Compose multiple hours_reduction effects (MULTIPLICATIVE_COMPOUNDING) ---
        composed_overrides, collision_warnings = self._compose_hours_overrides(
            pending_overrides=pending_overrides,
            base_hours_map=base_hours_map,
        )
        all_warnings.extend(collision_warnings)

        # --- Build derived work item states ----------------------------------
        work_item_states = self._build_work_item_states(
            base_hours_map=base_hours_map,
            hours_overrides=composed_overrides,
            prob_impacts=all_prob_impacts,
            all_warnings=all_warnings,
        )

        return PortfolioEffectsResult(
            effects=all_evaluations,
            work_item_states=work_item_states,
            commercial_option_states=all_option_states,
            cash_effects=all_cash_effects,
            warnings=all_warnings,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        effect: PortfolioEffect,
        context: PortfolioEvaluationContext,
        base_hours_map: dict[str, float],
        prob_impacts: dict[str, ProbabilisticHoursImpact],
        option_states_map: dict[str, CommercialOptionState],
        cash_effects: list[CashEffect],
    ) -> tuple[PortfolioEffectEvaluation, list[PortfolioWarning], dict[str, HoursOverride]]:
        """Dispatch an effect to its handler.

        Returns (evaluation, warnings, hours_overrides_from_this_effect).
        hours_overrides_from_this_effect is empty for non-hours effects.
        The engine accumulates them separately for compounding.
        """

        effect_type = effect.effect.get("type", "")

        # --- Validate trigger reference --------------------------------------
        if not context.work_item_exists(effect.trigger):
            warn = PortfolioWarning(
                code=PortfolioEffectCode.INVALID_PORTFOLIO_EFFECT_TRIGGER,
                severity=PortfolioEffectSeverity.ERROR,
                effect_id=effect.id,
                target_id=None,
                details={
                    "trigger_id": effect.trigger,
                    "effect_type": effect_type,
                    "reason": "Trigger work item not found in dataset.",
                },
            )
            evaluation = PortfolioEffectEvaluation(
                effect_id=effect.id,
                effect_type=effect_type,
                trigger_work_item_id=effect.trigger,
                targets=list(effect.targets),
                trigger_satisfied=False,
                deterministic=False,
                applied=False,
                warnings=[warn],
            )
            return evaluation, [warn], {}

        # --- Unsupported effect type -----------------------------------------
        if effect_type not in _SUPPORTED_TYPES:
            warn = PortfolioWarning(
                code=PortfolioEffectCode.UNSUPPORTED_PORTFOLIO_EFFECT_TYPE,
                severity=PortfolioEffectSeverity.ERROR,
                effect_id=effect.id,
                target_id=None,
                details={
                    "effect_type": effect_type,
                    "supported_types": sorted(_SUPPORTED_TYPES),
                },
            )
            evaluation = PortfolioEffectEvaluation(
                effect_id=effect.id,
                effect_type=effect_type,
                trigger_work_item_id=effect.trigger,
                targets=list(effect.targets),
                trigger_satisfied=False,
                deterministic=False,
                applied=False,
                warnings=[warn],
            )
            return evaluation, [warn], {}

        # --- Dispatch to type-specific handler -------------------------------
        if effect_type == "quality_prerequisite":
            evaluation = handle_quality_prerequisite(effect, context)
            return evaluation, list(evaluation.warnings), {}

        elif effect_type == "hours_reduction":
            evaluation, overrides = handle_hours_reduction(
                effect, context, base_hours_map
            )
            # Return overrides separately — compounding happens in evaluate()
            return evaluation, list(evaluation.warnings), overrides

        elif effect_type == "future_hours_reduction":
            evaluation, impacts = handle_future_hours_reduction(
                effect, context, base_hours_map
            )
            prob_impacts.update(impacts)
            return evaluation, list(evaluation.warnings), {}

        elif effect_type == "commercial_option_unlock":
            evaluation, option_states = handle_commercial_option_unlock(
                effect, context
            )
            for state in option_states:
                option_states_map[state.option_id] = state
            return evaluation, list(evaluation.warnings), {}

        elif effect_type == "cash_inflow":
            evaluation, cash_effect = handle_cash_inflow(effect, context)
            if cash_effect is not None:
                cash_effects.append(cash_effect)
            return evaluation, list(evaluation.warnings), {}

        # Should never reach here due to _SUPPORTED_TYPES guard above
        raise AssertionError(f"Unhandled effect type: {effect_type!r}")

    @staticmethod
    def _compose_hours_overrides(
        pending_overrides: dict[str, list[HoursOverride]],
        base_hours_map: dict[str, float],
    ) -> tuple[dict[str, HoursOverride], list[PortfolioWarning]]:
        """Compose multiple hours_reduction effects on the same target.

        Policy: MULTIPLICATIVE_COMPOUNDING (V1 modeling assumption, not a dataset fact).
            effective = base * (1 - r1) * (1 - r2) * ...

        This is order-independent for any finite set of positive reduction fractions
        because multiplication is commutative.  The net reduction fraction is:
            net_fraction = 1 - product(1 - ri)

        Parameters
        ----------
        pending_overrides:
            Mapping target_id -> list of per-effect HoursOverride records.
            Populated by _dispatch() during the effects loop.
        base_hours_map:
            Canonical base hours (source of truth; never mutated).

        Returns
        -------
        composed: dict[str, HoursOverride]
            Final override per target, with all applied_reductions combined.
        collision_warnings: list[PortfolioWarning]
            One HOURS_REDUCTION_COLLISION_COMPOUNDED warning per target where
            more than one active reduction was compounded.
        """
        composed: dict[str, HoursOverride] = {}
        collision_warnings: list[PortfolioWarning] = []

        for wid, overrides_for_target in pending_overrides.items():
            # Only keep overrides where applied=True (trigger was satisfied)
            active = [o for o in overrides_for_target if o.applied]

            if not active:
                # Trigger(s) not satisfied — use first override record (unapplied)
                composed[wid] = overrides_for_target[0]
                continue

            base_hours = base_hours_map.get(wid, overrides_for_target[0].base_required_hours)

            if len(active) == 1:
                # Simple case: single active reduction, no compounding needed
                composed[wid] = active[0]
            else:
                # Collision: multiple active reductions on same target
                # Combine via MULTIPLICATIVE_COMPOUNDING (policy = V1 assumption)
                keep_fraction = 1.0
                for o in active:
                    keep_fraction *= (1.0 - o.reduction_fraction)
                effective_hours = base_hours * keep_fraction
                net_reduction_fraction = 1.0 - keep_fraction

                # Collect all applied_reductions for traceability
                all_applied: list[AppliedReduction] = []
                for o in active:
                    all_applied.extend(o.applied_reductions)

                composed[wid] = HoursOverride(
                    base_required_hours=base_hours,
                    effective_required_hours=effective_hours,
                    reduction_fraction=net_reduction_fraction,
                    applied=True,
                    applied_reductions=all_applied,
                )

                collision_warnings.append(
                    PortfolioWarning(
                        code=PortfolioEffectCode.HOURS_REDUCTION_COLLISION_COMPOUNDED,
                        severity=PortfolioEffectSeverity.WARNING,
                        effect_id="(multiple)",
                        target_id=wid,
                        details={
                            "target_work_item_id": wid,
                            "base_required_hours": base_hours,
                            "effective_required_hours": effective_hours,
                            "net_reduction_fraction": net_reduction_fraction,
                            "combination_policy": "multiplicative_compounding",
                            "policy_note": (
                                "V1 modeling assumption: effective = base * "
                                "product(1 - ri). Not a dataset fact."
                            ),
                            "contributing_effects": [
                                {
                                    "effect_id": ar.effect_id,
                                    "trigger_work_item_id": ar.trigger_work_item_id,
                                    "reduction_fraction": ar.reduction_fraction,
                                }
                                for ar in all_applied
                            ],
                        },
                    )
                )

        return composed, collision_warnings

    @staticmethod
    def _build_work_item_states(
        base_hours_map: dict[str, float],
        hours_overrides: dict[str, HoursOverride],
        prob_impacts: dict[str, ProbabilisticHoursImpact],
        all_warnings: list[PortfolioWarning],
    ) -> dict[str, DerivedWorkItemState]:
        """Build derived work item states for all work items affected by effects."""
        affected_ids = set(hours_overrides.keys()) | set(prob_impacts.keys())

        # Also include any work items mentioned in warnings
        for w in all_warnings:
            if w.target_id and w.target_id in base_hours_map:
                affected_ids.add(w.target_id)

        states: dict[str, DerivedWorkItemState] = {}

        for wid in affected_ids:
            base_hours = base_hours_map.get(wid, 0.0)
            override = hours_overrides.get(wid)
            prob_impact = prob_impacts.get(wid)

            if override and override.applied:
                effective_hours = override.effective_required_hours
                override_applied = True
            else:
                effective_hours = base_hours
                override_applied = False

            item_warnings = [
                w for w in all_warnings
                if w.target_id == wid
            ]

            states[wid] = DerivedWorkItemState(
                work_item_id=wid,
                base_required_hours=base_hours,
                effective_required_hours=effective_hours,
                hours_override_applied=override_applied,
                probabilistic_hours=prob_impact,
                portfolio_warnings=item_warnings,
            )

        return states

    @staticmethod
    def build_context_from_dataset(
        dataset: CandidateDataset,
        completed_work_item_ids: frozenset[str] | None = None,
        selected_work_item_ids: frozenset[str] | None = None,
        notes: str | None = None,
    ) -> PortfolioEvaluationContext:
        """Convenience builder: create a PortfolioEvaluationContext from a dataset.

        Parameters
        ----------
        dataset:
            Source of truth for all valid IDs.
        completed_work_item_ids:
            Which work items are completed in this scenario. Defaults to empty.
        selected_work_item_ids:
            Which work items are selected. Defaults to empty.
        notes:
            Optional freeform scenario description.
        """
        return PortfolioEvaluationContext(
            completed_work_item_ids=completed_work_item_ids or frozenset(),
            selected_work_item_ids=selected_work_item_ids or frozenset(),
            all_work_item_ids=frozenset(w.id for w in dataset.work_items),
            all_commercial_option_ids=frozenset(
                o.option_id for o in dataset.commercial_options
            ),
            planning_date=dataset.metadata.planning_start,
            notes=notes,
        )
