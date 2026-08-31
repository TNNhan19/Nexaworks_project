# NexaWorks — Business Rules & Assumptions

This document separates rules supported directly by the supplied material from explicit modeling decisions chosen for the first implementation.

## Confirmed by supplied data / Data Dictionary

- `required_skills` are minimum levels that should be covered by assigned people.
- Skill levels for one requirement are not additive: two AI=3 people do not satisfy AI>=4.
- `mandatory=true` represents a business/safety/contract commitment but does not guarantee feasibility.
- `revenue_jpy` is committed-work revenue; sales opportunities obtain commercial values from `commercial_options`.
- `delivery_hours` is additional delivery effort if a commercial option is won.
- Dependencies describe items expected to be completed first.
- Portfolio effects may be modeled, approximated or explicitly excluded with explanation.

## V1 modeling decisions

| Topic | Policy | Interpretation |
|---|---|---|
| Work effort | `TOTAL_PERSON_HOURS` | `required_hours` is a shared person-hour pool across assigned people. |
| Skill coverage | `TEAM_COVERAGE` | Different requirements may be covered by different assigned people; a single skill level is never summed. |
| Language | `CUSTOMER_FACING_COVERAGE` | Required language is covered at the customer-facing / coordination level, not necessarily by every technical contributor. |
| Sales capacity | `FULL_IF_COMMITTED` | A chosen/accepted option must be deliverable at full `delivery_hours`; pending opportunities are shown separately as pipeline sensitivity. |
| Dependencies | `HARD` | Dependency order cannot be violated. |
| Contract/internal deadline | `SOFT_WITH_PENALTY` | Late completion may be scheduled but must show late days, penalty and at-risk status. |
| Sales opportunity deadline | `HARD_OR_EXPIRY` | Treat as opportunity expiry unless a future dataset gives a more specific rule. |
| Mandatory | `REQUIRED_TARGET` | Planner attempts to include it; if impossible, result is explicitly infeasible/at-risk. |
| Direct cost timing | `PRORATED_OVER_EXECUTION` | Cost is distributed over scheduled execution when no specific timing is provided. |
| Commercial options | `MUTUALLY_EXCLUSIVE` | At most one option per opportunity, or no-bid / renegotiate. |
| Planning | `DAY` | Scheduling granularity is one day. |
| Daily capacity | `EVEN_DISTRIBUTION_OVER_AVAILABLE_DAYS` | Horizon person capacity is spread evenly across inclusive available dates; no 8-hour day is invented. |
| Unavailable ranges | `INCLUSIVE` | Both range endpoints have zero daily capacity. |
| Exclusive resources | `ONE_ACTIVE_WORK_ITEM_PER_RESOURCE_PER_DAY` | Date-only V1 prevents two actions using one exclusive resource on the same day. |
| Commercial delivery timing | `RESERVED_CAPACITY` | Full delivery hours consume person capacity but are labeled reservation, not confirmed execution timing. |
| Probabilistic effects | `EXPECTED_VALUE + DOWNSIDE` | Expected value informs scoring; feasibility/risk also examines failure/downside scenarios. |

## Portfolio effect V1 treatment

- **E001 `quality_prerequisite`**: qualitative elevated-risk flag + explainable configurable score adjustment; never pretend the dataset specified an exact percentage.
- **E002 `hours_reduction`**: apply the stated 25% reduction when the trigger is completed first.
- **E003 `future_hours_reduction`**: expected benefit for value scoring; success/failure sensitivity for capacity planning.
- **E004 `commercial_option_unlock`**: hard availability condition for the option.
- **E005 `cash_inflow`**: expected cash value for comparison plus downside cash scenario where collection fails.

---

## Phase 2A — Feasibility Engine Implementation Notes

These notes capture decisions made during Phase 2A implementation that refine or clarify the policies above.

### Dependency status distinction

An unsatisfied HARD dependency does **not** make a work item permanently INFEASIBLE.

| Condition | Status |
|---|---|
| Dependency in `completed_ids` | SATISFIED → work item status unaffected |
| Dependency in dataset but not completed | **BLOCKED** (not INFEASIBLE) |

Rationale: the Planner (Phase 2E) may schedule the prerequisite before this item within the same horizon.  Permanent INFEASIBLE is reserved for structural impossibilities (e.g. missing skill).

### Deadline classification

Three-way classification with explicit boundary conditions:

| Condition | Status |
|---|---|
| `due_date < planning_date` | `EXPIRED` |
| `planning_date ≤ due_date ≤ planning_end` | `WITHIN_HORIZON` |
| `due_date > planning_end` | `OUTSIDE_HORIZON` |

- `OUTSIDE_HORIZON` is **not** the same as EXPIRED.
- `DEADLINE_AT_RISK` is **not** raised merely because a due date is within the horizon.  Schedule-based lateness belongs to Phase 2E.

### Capacity check pool

For the `TOTAL_PERSON_HOURS` check, the pool is the **entire team**, not just skill-eligible people.

Rationale: a person contributes labour hours to a work item even if someone else covers the required skill threshold.  Restricting the pool would produce false INFEASIBLE results.

### Language coverage configurability

`CUSTOMER_FACING_COVERAGE` is implemented via two new `AssumptionRegistry` fields:

| Field | Default | Effect |
|---|---|---|
| `language_customer_facing_skill` | `None` | Any speaker qualifies |
| `language_customer_facing_min_level` | `0.0` | Minimum level of the proxy skill |

Example: set `language_customer_facing_skill = "project_management"` and `language_customer_facing_min_level = 3` to require that a language speaker also has PM level ≥ 3 to count as customer-facing.

### Feasibility vs Scoring

Hard constraint violations are **never** converted to score penalties.

```
Required AI >= 4, no eligible employee:
  WRONG:  priority_score -= 30
  CORRECT: status=INFEASIBLE, reason=MISSING_SKILL_COVERAGE
```

Scoring (Phase 2D) operates exclusively on choices that are already operationally possible.

---

## Phase 2B -- Portfolio Effects Engine Implementation Notes

These notes capture decisions made during Phase 2B implementation.

### Canonical dataset NOT mutated

All derived values live in `PortfolioEffectsResult`. The original `CandidateDataset` is never modified. This is a hard architectural requirement.

### E001 is NOT a hard dependency

E001 (`quality_prerequisite`) produces a qualitative warning only. The BLOCKED status of W001/W006/W007 is caused exclusively by their own `work_item.dependencies = ["W005"]`, which Phase 2A's dependency checker handles. E001 adds an additional qualitative risk signal on top of (and independent of) the HARD dependency.

### Effect handlers dispatch on `effect.type`

All handlers are generic. No handler contains logic conditioned on E001/E002/W005/W013 etc.

### Deterministic vs probabilistic distinction

| Effect type | Category | Committed hours changed? |
|---|---|---|
| `hours_reduction` | Deterministic | YES (when trigger satisfied) |
| `future_hours_reduction` | Probabilistic | NO (scenarios preserved separately) |
| `cash_inflow` | Probabilistic | NO (expected/success/downside separated) |
| `quality_prerequisite` | Qualitative | NO (warning only) |
| `commercial_option_unlock` | Deterministic | N/A (option availability) |

### Portfolio-Feasibility integration

Feasibility Engine now accepts `effective_hours_override: dict[str, float] | None`. When provided, this replaces `required_hours` in the capacity check only. All 45 Phase 2A tests pass without changes because the parameter defaults to None.

### Multiple hours_reduction effects on the same target

When more than one active `hours_reduction` effect targets the same work item, the engine uses **MULTIPLICATIVE_COMPOUNDING**:

```
effective = base * (1 - r1) * (1 - r2) * ...
```

This is a V1 modeling assumption (not a dataset fact), documented in `AssumptionRegistry.hours_reduction_combination_policy`. The combination is order-independent (commutative). A `HOURS_REDUCTION_COLLISION_COMPOUNDED` warning with full traceability evidence is emitted. This is NOT last-writer-wins; the collision is explicitly detected and handled.

---

## Phase 2D -- Value / Priority Scoring Notes

- The default `BALANCED_V1` weights are explicit `AssumptionRegistry.scoring_weights` and sum to 1.0.
- Every component is normalized to 0–1 before weighting; no JPY value is directly added to a semantic rating.
- Unbounded value metrics use a reusable empirical-CDF `ScoringReference` built from the candidate-action set.
- N/A is distinct from zero and causes transparent effective-weight renormalization.
- Hard feasibility, blockers, locks, expiry, and invalidity remain separate `selection_status` facts and never become score penalties.
- `mandatory=true` is preserved for the Planner and never receives an artificial score bonus.
- Phase 2D scores canonical options only; planner-level `NO_BID` belongs to Phase 2E.

---

## Phase 2E -- Heuristic Planner Notes

- `BLOCKED`/`LOCKED` are re-evaluated after prerequisite completion; they are not permanent rejection states.
- Dependency and commercial-unlock closure is transitive, cycle-checked, and scheduled before the target.
- Mandatory work is attempted before score-ordered optional work, without overriding feasibility.
- Option selection uses full delivery commitment. Expected delivery hours never reduce reserved capacity.
- `NO_BID` is emitted only as a Planner decision when no canonical option is selected.
- Soft deadlines may be late with structured evidence; sales-opportunity expiry remains hard.
- Candidate attempts are transactional: a failed target does not leave speculative prerequisites consuming capacity.

---

## Phase 2F -- Cash-Flow Simulator Notes

- Starting cash and minimum buffer come from company data; neither is hard-coded.
- The horizon-only fixed outflow uses PRORATED_OVER_HORIZON with exact integer-JPY remainder allocation.
- Selected non-commercial direct costs use PRORATED_OVER_EXECUTION.
- Deterministic work receipts require committed=true and occur at completion plus cash_in_days.
- Positive noncommitted work revenue is not silently treated as guaranteed cash.
- Selected-option receipts use last reserved-delivery date plus payment_days.
- Commercial delivery cost is conditional on win: full/expected/zero in SUCCESS/EXPECTED/DOWNSIDE.
- E005 uses Phase 2B amount/probability and trigger completion plus trigger cash_in_days.
- Outside-horizon receipts remain future events and do not improve the four-week balance.
- Late penalty is excluded from cash by default because the Data Dictionary does not establish a cash obligation.

---

## Phase 2G -- Final Validation + Explanation Notes

These notes capture decisions made during Phase 2G implementation.

### No-replanning principle

Phase 2G validates and explains only. It receives frozen `PlanResult` and `CashFlowResult` and never:
- Calls `PlannerEngine` to fix or improve the plan.
- Calls `CashFlowSimulator` to recalculate cash.
- Modifies any upstream result object.
- Silently repairs a hard constraint violation.

If a violation is detected, it is returned as an `ExplanationRecord` with the appropriate severity.

### Status propagation rules (explicit)

1. `OPERATIONALLY_INFEASIBLE` → `PLAN_INFEASIBLE` (hard failure dominates).
2. Any scenario reaches `NEGATIVE_CASH` → at least `PLAN_AT_RISK`.
3. Any scenario reaches `BUFFER_BREACH` → at least `PLAN_AT_RISK`.
4. `OPERATIONALLY_AT_RISK` (mandatory infeasible or omitted) → `PLAN_AT_RISK`.
5. `CASH_AT_RISK` (from Phase 2F overall status) → `PLAN_AT_RISK`.
6. `OPERATIONALLY_PARTIAL` + `CASH_SAFE` → `PLAN_PARTIAL`.
7. `OPERATIONALLY_FEASIBLE` + `CASH_SAFE` → `PLAN_FEASIBLE`.

Financial severity order (worst wins): `NEGATIVE_CASH` > `BUFFER_BREACH` > `CASH_AT_RISK` > `CASH_SAFE`.

### Explanation provenance

Every `ExplanationRecord` carries a `source_phase` field. Phase 2G findings use `FINAL_VALIDATION`; forwarded findings from upstream phases preserve their original `source_phase` (`PLANNER`, `CASH_FLOW`, etc.).

### Localization policy

Phase 2G produces no natural-language strings. All output uses `ExplanationCode` enum values. Frontend `react-i18next` is responsible for JA / EN / VI translation.

### Cash Timing Mismatch

`CASH_TIMING_MISMATCH` is emitted when substantial future receipts exist but in-horizon cash becomes unsafe. This distinguishes "business is structurally solvent" from "the four-week window has a timing gap". Evidence includes: in-horizon outflows, in-horizon receipts, future receipts total, and expected ending cash.
