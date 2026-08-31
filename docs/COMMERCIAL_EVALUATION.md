# Commercial Evaluation — Phase 2C

## Purpose

Phase 2C deterministically describes the commercial and individual operational facts of every canonical work item that owns commercial options. It does not rank options or make a final choice.

> Commercial Evaluation is descriptive. Phase 2D scores real options; final `SELECT_OPTION(option_id)` or `NO_BID` belongs to the Phase 2E Planner.

## Inputs and composition

- `CandidateDataset` supplies opportunity effort and declared option facts.
- Phase 2B `PortfolioEffectsResult` is authoritative for option locks. Phase 2C does not recreate unlock effects.
- Phase 2A supplies skill, language, dependency, capacity, resource, and `HARD_OR_EXPIRY` deadline semantics.
- `AssumptionRegistry` remains unchanged: `FULL_IF_COMMITTED` and `MUTUALLY_EXCLUSIVE` are the approved policies.

The Data Dictionary defines `work_items.required_hours` as the item's initial effort estimate and `commercial_options.delivery_hours` as additional delivery effort if the option wins. `BUSINESS_RULES.md` confirms that sales-opportunity `required_hours` is base proposal/sales effort. The engine therefore preserves:

```text
base_opportunity_effort_hours = work_item.required_hours
committed_delivery_hours_if_won = commercial_option.delivery_hours
total_committed_hours_if_won = base + delivery
expected_delivery_hours = delivery × win_probability  # analysis only
```

Expected delivery hours never replace committed hours in a capacity check.

## Metrics

When their source fields are available and valid:

```text
gross_margin_jpy = price_jpy - direct_cost_jpy
gross_margin_ratio = gross_margin_jpy / price_jpy
expected_revenue_jpy = price_jpy × estimated_win_probability
expected_margin_jpy = gross_margin_jpy × estimated_win_probability
expected_follow_on_value_jpy = follow_on_value_jpy × estimated_win_probability
```

Zero price yields a `None` margin ratio and structured `ZERO_PRICE_OPTION` / `GROSS_MARGIN_RATIO_UNDEFINED` facts. Decimal arithmetic is used internally for JPY-derived values. Missing optional facts remain `None`; invalid probability is not clamped.

## Availability and deliverability

Availability is one of `AVAILABLE`, `LOCKED`, `EXPIRED`, or `INVALID`.

- Phase 2B controls `LOCKED`/unlocked state; canonically W007-B is locked until W022 is completed.
- Phase 2A `HARD_OR_EXPIRY` controls expiry for `sales_opportunity` work items.
- Duplicate option IDs, unknown references, missing required facts, and invalid/negative facts produce structured codes and `INVALID` availability.

Deliverability is checked individually by copying the parent work item, merging option dependencies, and setting required hours to effective base effort plus full delivery hours before calling Phase 2A. It may be `INDIVIDUALLY_DELIVERABLE`, `NOT_INDIVIDUALLY_DELIVERABLE`, `BLOCKED`, `LOCKED`, `EXPIRED`, or `INVALID`.

Individual deliverability does not mean all deals fit simultaneously. Portfolio selection and shared capacity allocation belong to Phase 2E.

## Canonical alternatives and cash facts

Phase 2C evaluates only `CommercialOption` records declared in the input dataset. It does not infer an option type from localized labels or from zero-valued price, cost, or delivery fields, and it does not synthesize a `NO_BID` option. Therefore W011-C (`No-bid`) and W012-B (`Do not apply`) remain ordinary canonical option evaluations with their original labels and metrics.

The input schema has no structured NO_BID/DECLINE discriminator. `NO_BID` is reserved for a later planner-level decision action:

```text
SELECT_OPTION(option_id)
OR
NO_BID
```

The result exposes `price_jpy`, `direct_cost_jpy`, option `payment_days`, and parent `cash_in_days`. It does not decide cash safety or simulate timing; that belongs to Phase 2F.

## Public interface and API

```python
engine = CommercialEvaluationEngine()
portfolio = engine.build_portfolio_context(dataset, completed_work_item_ids)
result = engine.evaluate(dataset, portfolio, completed_ids=completed_work_item_ids)
```

- `GET /api/v1/commercial`
- `GET /api/v1/commercial/{work_item_id}`

The core package has no FastAPI dependency.

## Dataset classification note

W012 is typed `corporate` but owns two of the canonical 18 commercial options. The engine evaluates every work item that owns options, so all canonical options remain represented without changing canonical data or the approved proposal.

## Deferred limitations

- No weighted score, ranking, recommendation, planner-level NO_BID action, optimizer, schedule, or simultaneous portfolio selection.
- No cash-flow simulation or `CASH_SAFE`/`CASH_UNSAFE` decision.
- Capacity is the Phase 2A structural team-capacity check; per-person and calendar feasibility remain Phase 2E work.
