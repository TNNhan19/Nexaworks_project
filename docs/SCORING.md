# Value / Priority Scoring — Phase 2D

## Purpose and boundary

Phase 2D converts supported facts into normalized, traceable business-value components and a 0–100 score. It does not select a portfolio, assign people, schedule work, simulate cash, or create planner-level `NO_BID` actions.

> Phase 2D ranks business value only. Phase 2E Planner makes the final constrained selection.

Eligibility remains separate from value. A BLOCKED, LOCKED, EXPIRED, INFEASIBLE, or INVALID candidate may retain a calculable score for explanation, but `eligible_for_selection` is false.

## Candidate actions

- A work item without commercial options becomes `DO_WORK_ITEM`, with `action_id = work_item.id`.
- Every canonical Phase 2C option becomes `SELECT_OPTION`, with `action_id = option.option_id`.
- A parent owning options is not also scored as `DO_WORK_ITEM`.
- Phase 2D never synthesizes or infers `NO_BID`. W011-C and W012-B remain ordinary canonical `SELECT_OPTION` candidates.

## BALANCED V1 weights

| Component | Weight |
|---|---:|
| Economic value | 0.30 |
| Strategic/customer | 0.20 |
| Urgency/cost of delay | 0.15 |
| Cash timing | 0.10 |
| Follow-on value | 0.10 |
| Capacity efficiency | 0.10 |
| Risk resilience | 0.05 |

Weights are immutable scenario assumptions in `AssumptionRegistry.scoring_weights`. Each must be non-negative and the total must equal 1 within `1e-9`.

## Component sources and formulas

### Economic value

- Option: Phase 2C `expected_margin_jpy` without recomputation.
- Work item: `(revenue_jpy - direct_cost_jpy) × success_probability` using Decimal arithmetic.
- Non-positive raw values normalize to 0 and negative values emit `NEGATIVE_ECONOMIC_VALUE`.

### Strategic/customer

Uses `work_item.strategic_value`. Although canonical values are 2–5, the schema does not declare a fixed range, so the current/reference candidate distribution is used. Customer reference/risk/reliability fields are not combined because the Data Dictionary does not define comparable scoring semantics.

### Urgency/cost of delay

```text
deadline_proximity = 1 - clamp(days_until_due / horizon_days, 0, 1)
late_penalty_percentile = ECDF(late_penalty_jpy_per_day)
urgency = 0.5 × deadline_proximity + 0.5 × late_penalty_percentile
```

Expired sales opportunities remain EXPIRED operationally. Deadline proximity never changes eligibility.

### Cash timing

Applicable only when a positive financial inflow and timing field exist:

- Option: positive `price_jpy` plus Phase 2C `payment_days`.
- Work: positive `revenue_jpy` plus `cash_in_days`.

```text
cash_timing = 1 / (1 + days_to_cash / horizon_days)
```

This is timing preference only, not a cash-buffer simulation.

### Follow-on value

Options reuse Phase 2C `expected_follow_on_value_jpy`. Zero is a real applicable value. Non-commercial work has no supported corresponding field and is N/A.

### Capacity efficiency

```text
capacity_efficiency = economic_value / committed_hours
```

- Option denominator: Phase 2C `total_committed_hours_if_won`—full committed hours, never expected delivery hours.
- Work denominator: Phase 2B `effective_required_hours`.

### Risk resilience

Only Phase 2B quality-prerequisite facts are supported in V1:

- `QUALITY_PREREQUISITE_SATISFIED` → 1.0
- `QUALITY_PREREQUISITE_RISK` → `AssumptionRegistry.scoring_quality_risk_resilience` (default 0.5)
- No applicable quality effect → N/A

Win probability is already present in expected commercial values and is not added again as a risk bonus.

## ScoringReference and normalization

Unbounded positive metrics use an empirical CDF over all valid current candidate actions:

```text
normalized(raw) = count(reference values <= raw) / count(reference values)
```

Only positive finite reference values enter these distributions. A non-positive raw economic/value metric is a real zero and normalizes to 0. Ties receive identical percentiles. Exact sorted values, counts, minima, and maxima are exposed in `ScoringReference`.

When no reference is supplied, the engine builds one with `reference_source = CURRENT_SNAPSHOT`. A baseline reference may later be passed unchanged into scenario runs; `reference_usage` then reports `REUSED`.

## N/A handling and trace

N/A is distinct from zero. For each candidate:

```text
effective_weight_i = configured_weight_i / sum(applicable configured weights)
weighted_contribution_i = normalized_value_i × effective_weight_i
business_value_score = round(100 × sum(weighted_contribution_i), 2)
```

N/A components expose `applicable=false`, `normalized_value=null`, and `effective_weight=0`. Every component returns its raw value, configured/effective weights, contribution, source, and formula evidence.

## Eligibility composition

- Non-commercial actions map Phase 2A FEASIBLE/BLOCKED/INFEASIBLE results.
- Option actions map Phase 2C availability and deliverability to ELIGIBLE/BLOCKED/LOCKED/EXPIRED/INFEASIBLE/INVALID.
- Mandatory is exposed as a fact only; it never changes the score.
- Scores never override `eligible_for_selection`.

## API

- `GET /api/v1/scoring`
- `GET /api/v1/scoring/{action_id}`

The API composes Phase 2B, Phase 2C, and Phase 2D through their public interfaces. The scoring core has no FastAPI dependency.

## Deferred limitations

- No customer-field composite because common scale/meaning is not declared.
- No conversion of future-hours effects to JPY.
- E005 collection is not treated as new profit; cash simulation remains Phase 2F.
- No portfolio selection, mutual-capacity allocation, assignment, schedule, optimizer, or planner-level NO_BID.
