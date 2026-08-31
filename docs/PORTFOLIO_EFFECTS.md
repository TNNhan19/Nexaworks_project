# Portfolio Effects Engine — Phase 2B Documentation

## Purpose

The Portfolio Effects Engine evaluates the five declared portfolio effects in the candidate dataset and produces a **Derived Decision Context** for downstream modules.

It answers:

> "Given the current scenario/context, which portfolio effects are applicable, what do they change, what risks/warnings do they create, and what uncertainty must downstream modules know about?"

---

## Conceptual Flow

```
Canonical Dataset
       |
       v
Scenario Snapshot (PortfolioEvaluationContext)
       |
       v
Portfolio Effect Evaluation (PortfolioEffectsEngine)
       |
       v
Derived Decision Context (PortfolioEffectsResult)
       |
       v
Commercial Evaluation / Feasibility / Scoring / Planner (later phases)
```

**Critical rule:** The canonical `CandidateDataset` is **never mutated.** All derived values live in `PortfolioEffectsResult`.

---

## Effect Types

### 1. `quality_prerequisite` (qualitative)

**Canonical example:** E001 — W005 -> W001, W006, W007

| Trigger state | Behavior |
|---|---|
| NOT satisfied | `QUALITY_PREREQUISITE_RISK` warning per target |
| Satisfied | `QUALITY_PREREQUISITE_SATISFIED` info per target |

**Critical constraints:**
- Does NOT create a hard dependency.
- Does NOT cause BLOCKED or INFEASIBLE status in the Feasibility Engine.
- Does NOT fabricate a numeric probability reduction or rework percentage.
- Qualitative risk only — no numeric business fact invented.

Phase 2D may optionally apply a configurable scoring penalty when `QUALITY_PREREQUISITE_RISK` is present.

---

### 2. `hours_reduction` (deterministic)

**Canonical example:** E002 — W013 -> W015 (25% reduction)

When the trigger is satisfied:

```
effective_required_hours = base_required_hours * (1 - reduction_fraction)
```

**Multiple effects on the same target (collision):**

When more than one active `hours_reduction` effect targets the same work item, the engine applies **MULTIPLICATIVE_COMPOUNDING** (V1 modeling assumption — not a dataset fact):

```
effective = base * (1 - r1) * (1 - r2) * ...

Example: base=100, r1=0.20, r2=0.25
  -> 100 * 0.80 * 0.75 = 60.0
```

This is **order-independent** (multiplication is commutative). The policy is registered in `AssumptionRegistry.hours_reduction_combination_policy = "multiplicative_compounding"`.

A `HOURS_REDUCTION_COLLISION_COMPOUNDED` warning is emitted with full evidence:
- `base_required_hours`
- `effective_required_hours`
- `net_reduction_fraction`
- `combination_policy` + `policy_note` (clearly labeled as a V1 assumption)
- `contributing_effects` list with `effect_id`, `trigger_work_item_id`, `reduction_fraction` per reduction

| Trigger state | Behavior |
|---|---|
| NOT satisfied | Effective hours = base hours, `HOURS_REDUCTION_NOT_APPLIED` code |
| Satisfied (single) | Effective hours reduced, `HOURS_REDUCTION_APPLIED` code |
| Satisfied (multiple on same target) | Compounded, `HOURS_REDUCTION_COLLISION_COMPOUNDED` warning |

**Critical constraints:**
- `base_required_hours` is always preserved separately.
- The reduction is **always calculated from the canonical base value**, never from a previously reduced value.
- Running the engine twice on the same context produces the **same result** (idempotent).
- Fractional hours are preserved (no silent truncation).

---

### 3. `future_hours_reduction` (probabilistic)

**Canonical example:** E003 — W017 -> W010, W019 (20% reduction, p=0.75)

This is probabilistic. Two scenarios are always preserved:

```
expected_impact_fraction = probability * impact_fraction   # e.g., 0.75 * 0.20 = 0.15

success_case_hours  = base * (1 - impact_fraction)        # e.g., 100 * 0.80 = 80h
downside_case_hours = base                                 # e.g., 100h unchanged
```

| Trigger state | Behavior |
|---|---|
| NOT satisfied | Both scenarios equal base hours, `FUTURE_HOURS_REDUCTION_TRIGGER_NOT_SATISFIED` |
| Satisfied | Eligible: `FUTURE_HOURS_REDUCTION_POSSIBLE`, both scenarios populated |

**Critical distinction:**

> **Expected Business Value ≠ Guaranteed Operational Capacity**

The operational committed plan uses **base hours** — NOT the expected reduction. Phase 2F (Cash-flow Simulator) handles sensitivity analysis across scenarios.

---

### 4. `commercial_option_unlock` (deterministic)

**Canonical example:** E004 — W022 -> commercial option W007-B

| Trigger state | Availability |
|---|---|
| NOT satisfied | `LOCKED` — `COMMERCIAL_OPTION_LOCKED` reason code |
| Satisfied | `AVAILABLE` — `COMMERCIAL_OPTION_UNLOCKED` reason code |

**Critical constraints:**
- Does NOT rank the option.
- Does NOT select the option.
- Options not referenced by any unlock effect are **available by default**.
- Phase 2C (Commercial Evaluation) handles ranking and selection.

---

### 5. `cash_inflow` (probabilistic)

**Canonical example:** E005 — W021 -> company_cash (+¥3.8M, p=0.85)

Three values are always computed separately:

```
expected_cash_inflow_jpy          = probability * cash_inflow_jpy   # e.g., 0.85 * 3.8M = ¥3.23M
success_case_cash_inflow_jpy      = cash_inflow_jpy                 # ¥3.8M
downside_case_cash_inflow_jpy     = 0                               # collection fails
```

**Critical constraints:**
- Do NOT add the expected value to committed cash and call the plan safe.
- Phase 2B prepares structured effect metadata only.
- Phase 2F (Cash-flow Simulator) handles buffer simulation and timeline.

---

## Activation Context

`PortfolioEvaluationContext` carries all state needed to evaluate effects:

| Field | Description |
|---|---|
| `completed_work_item_ids` | Work items completed in this scenario (trigger evaluation) |
| `selected_work_item_ids` | For future use by Planner |
| `all_work_item_ids` | Used to validate trigger/target references |
| `all_commercial_option_ids` | Used to validate option-unlock targets |
| `planning_date` | Reference date |
| `notes` | Optional scenario description |

For deterministic effects: trigger is satisfied ↔ `trigger_id in completed_work_item_ids`.

For probabilistic effects: "applicable" means the trigger is satisfied; the outcome is not yet realized. Both success and downside cases are always computed.

**No random sampling.** The engine is fully deterministic: same context → same result.

---

## Idempotency

Running the engine twice on the same canonical dataset and context produces identical results:
- Hours are always derived from `base_required_hours` — never from a previously reduced value.
- Cash effects are always derived from the declared `value_jpy` — never accumulated.
- Option states are set by the trigger state — no stacking.

This is a first-class design requirement. Tests 6 and the idempotency test in `test_portfolio_quality_hours.py` explicitly verify this.

---

## Integration with Phase 2A Feasibility Engine

The Feasibility Engine accepts an optional `effective_hours_override: dict[str, float]` parameter. When provided, capacity checks use the effective hours instead of canonical `required_hours`.

**Correct integration pattern:**

```python
# 1. Run Portfolio Effects Engine
pe_engine = PortfolioEffectsEngine()
pe_context = PortfolioEffectsEngine.build_context_from_dataset(dataset, completed_ids)
pe_result = pe_engine.evaluate(dataset, pe_context)

# 2. Build override map from deterministic effects only
override_map = {
    wid: state.effective_required_hours
    for wid, state in pe_result.work_item_states.items()
    if state.hours_override_applied
}

# 3. Run Feasibility Engine with effective hours
fe = FeasibilityEngine()
results = fe.check_all(dataset, effective_hours_override=override_map)
```

**The Feasibility Engine knows:** "effective required hours = 51h"

**The Feasibility Engine does NOT know:** "E002 caused 25% reduction because W013 triggered."

That trace lives in `PortfolioEffectsResult`. The separation is intentional.

---

## Result Structure

`PortfolioEffectsResult` top-level fields:

| Field | Type | Description |
|---|---|---|
| `effects` | `list[PortfolioEffectEvaluation]` | One per declared effect; full traceability |
| `work_item_states` | `dict[str, DerivedWorkItemState]` | Keyed by work_item_id; affected items only |
| `commercial_option_states` | `dict[str, CommercialOptionState]` | Keyed by option_id |
| `cash_effects` | `list[CashEffect]` | One per cash_inflow effect |
| `warnings` | `list[PortfolioWarning]` | All warnings flattened |

Key accessors:

```python
# Effective hours for capacity planning (falls back to base if no override)
result.get_effective_hours("W015", base_hours=68.0)

# Commercial option availability
result.is_option_available("W007-B")
```

---

## Reason / Warning Codes

All codes are machine-readable enums in `portfolio/reason_codes.py`. No localized strings.

| Code | Severity | When |
|---|---|---|
| `QUALITY_PREREQUISITE_RISK` | WARNING | Prerequisite not completed |
| `QUALITY_PREREQUISITE_SATISFIED` | INFO | Prerequisite completed |
| `HOURS_REDUCTION_APPLIED` | INFO | Deterministic reduction applied |
| `HOURS_REDUCTION_NOT_APPLIED` | INFO | Trigger not satisfied |
| `FUTURE_HOURS_REDUCTION_POSSIBLE` | INFO | Probabilistic, trigger eligible |
| `FUTURE_HOURS_REDUCTION_TRIGGER_NOT_SATISFIED` | INFO | Trigger not satisfied |
| `COMMERCIAL_OPTION_LOCKED` | WARNING | Unlock trigger not satisfied |
| `COMMERCIAL_OPTION_UNLOCKED` | INFO | Unlock trigger satisfied |
| `PROBABILISTIC_CASH_INFLOW` | INFO | Cash inflow eligible |
| `CASH_INFLOW_TRIGGER_NOT_SATISFIED` | INFO | Trigger not satisfied |
| `INVALID_PORTFOLIO_EFFECT_TARGET` | ERROR | Target ID not in dataset |
| `INVALID_PORTFOLIO_EFFECT_TRIGGER` | ERROR | Trigger ID not in dataset |
| `UNSUPPORTED_PORTFOLIO_EFFECT_TYPE` | ERROR | Unknown effect.type |

---

## Validation

Phase 2B defends against malformed effects in unseen datasets:
- Unknown trigger work item → `INVALID_PORTFOLIO_EFFECT_TRIGGER`
- Unknown work item target → `INVALID_PORTFOLIO_EFFECT_TARGET`
- Unknown commercial option target → `INVALID_PORTFOLIO_EFFECT_TARGET`
- Unsupported effect type → `UNSUPPORTED_PORTFOLIO_EFFECT_TYPE`

All validation produces structured `PortfolioWarning` results — no unhandled exceptions.

---

## Limitations (Deferred)

| Limitation | Deferred to |
|---|---|
| Cash-flow buffer simulation | Phase 2F |
| Commercial option ranking and selection | Phase 2C |
| Scoring adjustments for `QUALITY_PREREQUISITE_RISK` | Phase 2D |
| Multiple deterministic effects targeting the same work item (last-writer-wins) | Future |
| Sensitivity analysis across probabilistic scenarios | Phase 2F |
| Schedule-based trigger activation (trigger completed before a date) | Phase 2E/2F |

---

## Files

```
backend/app/decision_engine/portfolio/
  __init__.py                         Public exports
  context.py                          PortfolioEvaluationContext
  reason_codes.py                     PortfolioEffectCode, PortfolioEffectSeverity
  models.py                           All result Pydantic models
  engine.py                           PortfolioEffectsEngine orchestrator
  handlers/
    __init__.py
    quality_prerequisite.py           quality_prerequisite handler
    hours_reduction.py                hours_reduction handler (deterministic)
    future_hours_reduction.py         future_hours_reduction handler (probabilistic)
    commercial_option_unlock.py       commercial_option_unlock handler
    cash_inflow.py                    cash_inflow handler (probabilistic)

backend/app/api/portfolio.py          FastAPI adapter (GET /api/v1/portfolio)
backend/tests/test_portfolio_quality_hours.py
backend/tests/test_portfolio_probabilistic_commercial.py
backend/tests/test_portfolio_integration.py
backend/tests/conftest_portfolio.py
backend/scripts/run_portfolio_analysis.py

docs/PORTFOLIO_EFFECTS.md             This file
```
