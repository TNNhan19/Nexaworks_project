# Phase 2G — Final Validation + Explanation

## Purpose

Phase 2G is the terminal stage of the Decision Engine pipeline.  It integrates the outputs of:

- **Phase 2E** (`PlanResult`) — selected actions, schedule, assignments, capacity
- **Phase 2F** (`CashFlowResult`) — scenario cash positions, buffer breaches, future receipts

It answers: *"Is the generated plan operationally valid, financially acceptable or at risk, and why?"*

Phase 2G **validates and explains only**. It never:
- Replans or reschedules work items
- Rescores commercial options
- Recalculates cash flows
- Modifies any upstream result object

---

## Dimensional Status Model

Phase 2G uses three independent status dimensions rather than a single boolean.

### `OperationalStatus`

| Value | Meaning |
|---|---|
| `OPERATIONALLY_FEASIBLE` | No hard violations; all mandatory items accounted for; no delays |
| `OPERATIONALLY_PARTIAL` | Structurally valid; some optional items delayed or opportunities no-bid |
| `OPERATIONALLY_AT_RISK` | One or more mandatory items were explicitly reported infeasible |
| `OPERATIONALLY_INFEASIBLE` | Hard constraint violation detected during Phase 2G recheck |

### `FinancialStatus`

| Value | Meaning |
|---|---|
| `CASH_SAFE` | EXPECTED is safe and DOWNSIDE is safe |
| `CASH_AT_RISK` | EXPECTED is safe, but DOWNSIDE breaches the buffer or becomes negative |
| `BUFFER_BREACH` | EXPECTED falls below `minimum_cash_buffer_jpy` but stays non-negative |
| `NEGATIVE_CASH` | EXPECTED produces negative cash |

SUCCESS remains visible as supporting scenario evidence but does not drive aggregate financial status.

### `OverallStatus`

| Value | Meaning |
|---|---|
| `PLAN_FEASIBLE` | All mandatory items handled; no hard violations; cash safe |
| `PLAN_PARTIAL` | Operational partial (delays/no-bids) but no hard failures; cash safe |
| `PLAN_AT_RISK` | Mandatory item infeasible, or any cash scenario ends negative or below buffer |
| `PLAN_INFEASIBLE` | Hard operational constraint violation — plan cannot execute as stated |

---

## Status Propagation Rules

These rules are explicit, documented, and implemented in `engine.py`:

```
1. OPERATIONALLY_INFEASIBLE → PLAN_INFEASIBLE
   (hard operational failure dominates all other dimensions)

2. FinancialStatus == NEGATIVE_CASH → PLAN_AT_RISK
   (EXPECTED reaching negative cash is a critical risk)

3. FinancialStatus == BUFFER_BREACH → PLAN_AT_RISK
   (an EXPECTED buffer breach prevents PLAN_FEASIBLE or PLAN_PARTIAL)

4. OperationalStatus == OPERATIONALLY_AT_RISK → PLAN_AT_RISK
   (mandatory item failure is a significant risk)

5. FinancialStatus == CASH_AT_RISK → PLAN_AT_RISK

6. OperationalStatus == OPERATIONALLY_PARTIAL + CASH_SAFE → PLAN_PARTIAL

7. OperationalStatus == OPERATIONALLY_FEASIBLE + CASH_SAFE → PLAN_FEASIBLE
```

**Key invariant:** An unsafe DOWNSIDE makes aggregate status at least `CASH_AT_RISK` and overall status at least `PLAN_AT_RISK`, even when EXPECTED is safe.

---

## Validation Rules

### A. Mandatory Work
- Every `mandatory=true` work item must appear in `plan.selected_actions` or `plan.mandatory_infeasible`.
- Items in neither list trigger `MANDATORY_WORK_OMITTED` (ERROR) and make the supplied plan operationally infeasible.

### B. Dependency Ordering
- Canonical `work_item.dependencies` define predecessor relationships; selected decisions map work-item IDs to planner action IDs.
- Earliest and final scheduled dates are derived from the authoritative `PlanResult.schedule` records, not optional `PlanDecision.details` metadata.
- For each selected item with dependencies, its predecessor's final scheduled date must be strictly before the dependent's earliest scheduled date, matching Planner semantics.
- Violation triggers `DEPENDENCY_ORDER_VIOLATION` (ERROR).
- A selected dependency participant without schedule records triggers `SELECTED_ACTION_SCHEDULE_MISSING` (ERROR); validation is never silently skipped.

### C. Skill Coverage (TEAM_COVERAGE policy)
- Each required skill on a selected work item must be covered by at least one assigned person individually meeting the minimum level.
- Skill levels are never summed across people.
- Violation triggers `SKILL_COVERAGE_VIOLATION` (ERROR).

### D. Language Coverage (CUSTOMER_FACING_COVERAGE policy)
- Each required language must be covered by at least one assigned person who:
  - speaks the language, AND
  - meets the `language_customer_facing_skill` / `language_customer_facing_min_level` threshold (if configured).
- Violation triggers `LANGUAGE_COVERAGE_VIOLATION` (ERROR).

### E. Person Horizon Capacity
- `used_hours` must not exceed `capacity_hours` for any person.
- Violation triggers `PERSON_CAPACITY_EXCEEDED` (ERROR).

### F. Daily Capacity
- Per-person per-day scheduled hours must not exceed the person's daily capacity.
- Violation triggers `DAILY_CAPACITY_EXCEEDED` (WARNING).

### G. Unavailable Days
- No person may be scheduled on a day in their `unavailable_ranges`.
- Violation triggers `UNAVAILABLE_DAY_SCHEDULED` (ERROR).

### H. Resource Capacity Ceiling
- `used_hours` must not exceed `capacity_hours` for any shared resource.
- Violation triggers `RESOURCE_CAPACITY_EXCEEDED` (ERROR).

### I. Exclusive Resource Double-Booking
- No two different action IDs may use the same exclusive resource on the same day.
- Policy: `ONE_ACTIVE_WORK_ITEM_PER_RESOURCE_PER_DAY`.
- Violation triggers `RESOURCE_EXCLUSIVITY_VIOLATION` (ERROR).

### J. Commercial Exclusivity
- At most one `SELECT_OPTION` decision is allowed per work item (opportunity).
- Violation triggers `COMMERCIAL_EXCLUSIVITY_VIOLATION` (ERROR).
- A `NO_BID` coexisting with `SELECT_OPTION` for the same opportunity triggers `NO_BID_CONFLICTS_WITH_SELECTED_OPTION` (ERROR).

### K. Option Unlock / Expiry
- A `SELECT_OPTION` for a `sales_opportunity` whose `due_date < planning_start` triggers `OPTION_EXPIRED_AT_SELECTION` (CRITICAL).

### L. Earliest-Start
- Scheduled `start_date` must be ≥ `work_item.earliest_start`.
- Violation triggers `EARLIEST_START_VIOLATED` (ERROR).

---

## Explanation Provenance

Every `ExplanationRecord` carries a `source_phase` field identifying which upstream phase produced the evidence:

| `source_phase` | Origin |
|---|---|
| `FEASIBILITY` | Phase 2A |
| `PORTFOLIO` | Phase 2B |
| `COMMERCIAL` | Phase 2C |
| `SCORING` | Phase 2D |
| `PLANNER` | Phase 2E |
| `CASH_FLOW` | Phase 2F |
| `FINAL_VALIDATION` | Phase 2G recheck |

This prevents Phase 2G from becoming a black box and allows the frontend to link findings back to their originating phase.

---

## No-Replanning Principle

`FinalValidationEngine.validate()` receives frozen Pydantic models (`PlanResult`, `CashFlowResult`).
It never calls `PlannerEngine`, `CashFlowSimulator`, or any scoring/feasibility engine.
If validation detects a failure, it returns an `ExplanationRecord` with the appropriate severity.
**It does not silently fix the failure.**

---

## Cash Timing Mismatch

When substantial future receipts exist but in-horizon cash becomes unsafe, Phase 2G emits a `CASH_TIMING_MISMATCH` finding with evidence:

```json
{
  "code": "CASH_TIMING_MISMATCH",
  "severity": "WARNING",
  "source_phase": "CASH_FLOW",
  "evidence": {
    "in_horizon_outflows_jpy": ...,
    "in_horizon_receipts_jpy": ...,
    "future_receipts_total_expected_jpy": ...,
    "expected_ending_cash_jpy": ...,
    "future_receipt_sources": [...]
  }
}
```

This finding distinguishes "business is structurally solvent" from "four-week window has a timing gap".

---

## API

```
POST /api/v1/final-decision
```

**Request body** (all fields optional):

```json
{
  "plan": { ... },
  "cash_result": { ... },
  "completed_work_item_ids": []
}
```

If `plan` is omitted, Phase 2E is run automatically.
If `cash_result` is omitted, Phase 2F is run automatically on the plan.
Phase 2G validates and explains only — never replans.

**Response**: `FinalDecisionResult` (see `models.py`).

---

## Output Model Overview

```
FinalDecisionResult
  overall_status          OverallStatus
  operational_status      OperationalStatus
  financial_status        FinancialStatus

  executive_summary       ExecutiveSummary
    plan_status
    selected_count
    delayed_count
    no_bid_count
    mandatory_total / scheduled / infeasible
    capacity totals
    expected / downside / success ending cash
    minimum_cash / first_buffer_breach_date
    major_risks[]          [ExplanationCode strings]
    major_strengths[]      [ExplanationCode strings]

  mandatory_summary       MandatorySummary
  capacity_summary        CapacitySummary
  resource_summary        ResourceSummary
  cash_summary            CashSummary

  decision_explanations[] DecisionExplanation
  validations[]           ExplanationRecord
  warnings[]              ExplanationRecord
  critical_issues[]       ExplanationRecord
  explanation_records[]   ExplanationRecord (all findings flat)

  source_versions         dict  ("planner": "2E", "cash_flow": "2F", ...)
  assumptions_used        dict
```

---

## Localization

Phase 2G produces **no natural-language strings**.
All output uses structured `ExplanationCode` enum values.
The frontend uses `react-i18next` to translate codes into JA / EN / VI.

---

## Determinism

```
same dataset + same assumptions + same Phase 2E/2F results → identical FinalDecisionResult
```

No random behavior. No global mutable state.

---

## Known Limitations (V1)

- Skill and language coverage recheck relies on `plan.assignments`; a missing assignment record will cause the check to see "no assigned people" which may produce false violations.
- Cash severity uses the `worst scenario wins` rule; if the dataset includes only a SUCCESS scenario, it will drive the financial status.
- Phase 2G does not re-run the feasibility engine; it rechecks using structured data from the plan result only.
