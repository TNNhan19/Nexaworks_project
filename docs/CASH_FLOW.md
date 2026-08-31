# Cash-Flow Simulator — Phase 2F

## Boundary

Phase 2F evaluates a concrete Phase 2E operational plan as supplied. It creates independent EXPECTED, DOWNSIDE, and SUCCESS daily ledgers, but never changes selection, assignment, or schedule.

> Phase 2F validates cash-flow only. Phase 2G performs final integrated validation and explanation.

## Sources

- Canonical company data: starting cash, four-week fixed outflow, desired minimum buffer.
- Selected Phase 2E actions and their execution/reservation dates.
- Work-item committed revenue, direct cost, cash delay, and actual completion.
- Phase 2C selected-option price, direct cost, payment days, and win probability.
- Phase 2B cash effects, activated by actual plan completion context.

Phase 2D scoring values are never used as cash.

## Exact JPY

Money is converted through Decimal and stored as integer JPY. Probability-weighted values use deterministic half-up rounding to the nearest yen. Proration uses quotient/remainder allocation; earliest dates receive the remainder. Therefore every prorated source total reconciles exactly with no one-yen drift.

## Timing policies

### Fixed outflow

The source declares only a horizon total. PRORATED_OVER_HORIZON distributes it across every inclusive planning date while preserving the exact total.

### Work direct cost

PRORATED_OVER_EXECUTION distributes selected non-commercial work cost across unique actual execution dates from Phase 2E.

### Work receipts

Revenue is not immediate cash. A deterministic work receipt is scheduled only when committed=true and cash_in_days exists:

    receipt date = actual completion date + cash_in_days

The Data Dictionary says work-item revenue is associated with committed work. Positive revenue on a noncommitted item is therefore excluded with UNCOMMITTED_WORK_REVENUE_EXCLUDED; generic success_probability is not guessed into a cash formula.

### Commercial option

The schema does not define a payment anchor, so V1 uses:

    receipt date = last RESERVED_DELIVERY date + payment_days

Option direct_cost_jpy is treated as delivery cost conditional on winning and prorated across reserved-delivery dates. The parent work-item cost is not also charged because the source does not declare it as a separate proposal cost.

| Scenario | Receipt | Delivery cost |
|---|---:|---:|
| SUCCESS | full price | full option cost |
| EXPECTED | price × win probability | cost × win probability |
| DOWNSIDE | zero | zero |

Probability affects cash scenarios only; committed operational capacity remains full.

### E005

E005 amount/probability come from Phase 2B. Timing uses the completed trigger work item plus its structured cash_in_days. Canonically, W021 completion + 3 days produces the E005 date. SUCCESS receives the full amount, EXPECTED receives the probability-weighted amount, and DOWNSIDE records zero.

### Late penalties

late_penalty_jpy_per_day has no Data Dictionary cash/payment semantics. The default NOT_INCLUDED_WITHOUT_CASH_SEMANTICS policy emits a warning rather than inventing cash. AT_COMPLETION is configurable for a future scenario backed by a confirmed contractual cash obligation.

## Daily ledger and future events

Every inclusive horizon date contains opening cash, cash in/out, net change, closing cash, buffer headroom, breach flags, negative-cash flag, and traceable events.

Events dated after planning end are retained as future_events and do not change current closing cash. This separates revenue/receivables from cash physically received during the four weeks.

## Status

Per scenario:

- CASH_SAFE: closing cash never drops below the desired buffer.
- BUFFER_BREACH: below buffer but never negative.
- NEGATIVE_CASH: at least one negative closing balance.

Overall status is CASH_SAFE only when all scenarios are safe; otherwise it is CASH_AT_RISK. An expected-value improvement never hides a downside breach.

## API

POST /api/v1/cash-flow accepts an optional complete PlanResult. If omitted, the adapter generates the canonical Phase 2E plan first. The simulator itself has no FastAPI dependency.

## Limitations

- Fixed-outflow dates are modeled because the source supplies only a horizon total.
- Commercial payment anchor and conditional delivery-cost semantics are explicit V1 assumptions.
- Uncommitted work revenue is not forecast because work-type probability semantics are undefined.
- Future receivables are recorded but collections beyond the horizon are not simulated.
- Phase 2F does not replan or make the final integrated feasibility statement.
