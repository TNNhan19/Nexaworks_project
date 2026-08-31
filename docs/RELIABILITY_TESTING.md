# Phase 3 — Reliability and Unseen-Data Testing

## Purpose

Phase 3 proves that the completed Decision Engine operates from validated dataset structure rather than canonical NexaWorks identifiers, counts, rankings, or option suffixes. It adds synthetic tests and small test utilities; it does not introduce scenario APIs, frontend behavior, or new business rules.

## Dynamic-data philosophy

Production behavior must be derived from `CandidateDataset`, `PlanResult`, and `CashFlowResult`. Tests intentionally use identifiers such as `EMP_ALPHA`, `TASK_RED`, `GPU_CLUSTER`, and `OPTION_PREMIUM`. Canonical identifiers may remain in canonical regression tests, examples, documentation, and analysis scripts, but they must not control generic engine behavior.

The production-code audit covers work/person/resource IDs, canonical counts, and A/B/C option-suffix assumptions. Literal canonical IDs found in production modules are limited to docstrings or comments.

## Synthetic fixture strategy

Reusable factories live in `backend/tests/reliability/factories.py`:

- `make_person(...)`
- `make_customer(...)`
- `make_work_item(...)`
- `make_commercial_option(...)` via `make_option(...)`
- `make_resource(...)`
- `make_portfolio_effect(...)` via `make_effect(...)`
- `make_dataset(...)`
- `run_pipeline(...)`

Tests build compact same-schema datasets targeted to one behavior. This keeps failures attributable and avoids replacing the canonical dataset with another monolith.

## Coverage categories

- Dynamic sizes: 1/3/12 people, 1/5/31 work items, 0/1/5 options, 0/4 effects, and 0/1/4 resources.
- Non-canonical IDs: arbitrary people, work, resource, option, and effect identifiers across all phases.
- Skills and languages: unseen skill keys, independent TEAM_COVERAGE witnesses, non-summation of levels, and EN/JA/VI/FR workforce requirements.
- Dependencies: chain, fan-in, fan-out, cycles, pre-horizon completion, in-horizon completion, missing schedule, and order violation.
- Mandatory work: feasible closure, insufficient capacity, missing skills, impossible resources, explicit infeasibility, and silent omission.
- Capacity and availability: exact/insufficient/zero/fractional capacity, uneven teams, full-horizon unavailability, overlapping ranges, and inclusive endpoints.
- Shared resources: none, exact capacity, over-capacity, exclusive conflicts, independent same-day resources, missing references, arbitrary IDs, and more than two resources.
- Commercial options: arbitrary counts/IDs, zero value, zero delivery, probability boundaries, mutual exclusion, planner-level NO_BID, locks/unlocks, and expiry.
- Portfolio effects: all supported effect types, multiplicative compounding, order independence, and structured unsupported-type handling.
- Scoring: single/tied candidates, zero values, reusable normalization references, deterministic tie-breaking, and no mandatory bonus.
- Cash flow: absent cash facts, horizon boundaries, exact integer-JPY proration/reconciliation, buffer boundaries, negative starting cash, and multiple future receipts.
- Final validation: feasible/partial/at-risk/infeasible combinations, mandatory omission, dependency schedule evidence, and immutability.
- Malformed inputs: duplicate IDs, broken customer/dependency/resource/option/effect references, invalid probabilities/hours/capacity, and invalid dates.

## End-to-end unseen dataset

`test_end_to_end_unseen.py` validates and runs a compact arbitrary-ID dataset through:

```
CandidateDataset
→ Feasibility
→ Portfolio Effects
→ Commercial Evaluation
→ Scoring
→ Planner
→ Cash Flow
→ Final Validation
```

It includes unseen skills, FR workforce capability, a dependency, an exclusive resource, a commercial unlock, a selected option, deterministic work cash, probabilistic portfolio cash, and exact fixed outflow.

## Determinism

Representative unseen inputs run through every phase three times. Serialized feasibility, effects, commercial metrics, scores, plan, cash flow, and final validation results must be identical. Portfolio compounding is also checked with reversed effect declaration order.

## Malformed-input handling

Pydantic rejects invalid scalar constraints such as negative required hours/capacity, invalid probability, and malformed dates. `validate_references()` rejects duplicate or missing cross-entity references before engine execution. Unsupported portfolio effect types follow the established structured-warning policy instead of crashing.

## Production reliability fix

Phase 3 exposed one generic status-propagation defect: a mandatory item silently absent from a supplied planner result produced `MANDATORY_WORK_OMITTED` but was classified only as operationally at risk. It is now a hard structural recheck failure, producing `OPERATIONALLY_INFEASIBLE` and `PLAN_INFEASIBLE`. Explicit planner-reported `mandatory_infeasible` remains `OPERATIONALLY_AT_RISK`.

## Known remaining limitations

- The JSON Schema primarily checks structure and required fields; Pydantic and `validate_references()` provide most scalar and semantic validation.
- `PortfolioEffect.effect` is intentionally extensible. Unsupported effect types are reported by the Portfolio engine rather than rejected by JSON Schema.
- Workforce language identifiers are dataset-defined. UI translation support remains a separate JA/EN/VI concern.
- Financial aggregation follows the approved V1 scenario policy: EXPECTED drives explicit `NEGATIVE_CASH`/`BUFFER_BREACH`, an unsafe DOWNSIDE with safe EXPECTED maps to `CASH_AT_RISK`, and SUCCESS remains supporting evidence.
- Cash receipt timing uses planner completion metadata. Missing timing produces structured cash warnings rather than inferred dates.
- Phase 3 tests same-schema in-memory datasets and loader validation; it does not add a scenario persistence or execution API.
