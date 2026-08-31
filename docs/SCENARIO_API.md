# Phase 4 — Scenario API

Phase 4 exposes the completed decision engine through a synchronous FastAPI
application service. Canonical JSON and schema files remain read-only.

## Lifecycle and immutable baseline

A scenario stores a name, description, status, timestamps, and structured
overrides. Each effective input is built from a fresh canonical baseline plus
validated scenario overrides.

Overrides are applied to a deep copy. The resulting CandidateDataset is
validated with the existing Pydantic domain model and semantic reference
validator before the scenario is saved or run. No scenario can mutate the
canonical baseline or another scenario.

Endpoints:

- GET /api/v1/baseline/summary
- GET or POST /api/v1/scenarios
- GET, PATCH, or DELETE /api/v1/scenarios/{scenario_id}
- POST /api/v1/scenarios/{scenario_id}/run
- GET /api/v1/scenarios/{scenario_id}/runs
- GET /api/v1/runs/{run_id}
- GET /api/v1/runs/compare?run_a_id=...&run_b_id=...

Existing diagnostic endpoints and GET /health remain available.

## Override format

Only declared fields are accepted; arbitrary field injection is rejected.
Targets must already exist in the baseline. A representative request is:

    {
      "name": "Higher opening cash",
      "description": "Liquidity sensitivity",
      "overrides": {
        "company": {"starting_cash_jpy": 18000000},
        "people": [
          {"person_id": "P001", "capacity_hours": 96}
        ],
        "work_items": [
          {"work_item_id": "W001", "required_hours": 100, "dependencies": ["W005"]}
        ],
        "commercial_options": [
          {"option_id": "W006-A", "estimated_win_probability": 0.65}
        ],
        "resources": [
          {"resource_id": "R001", "capacity_hours": 120, "exclusive": true}
        ]
      }
    }

Supported groups cover company cash/buffer/outflow, person capacity and
unavailability, work effort/dates/cash/dependencies, commercial
price/cost/hours/payment/probability/dependencies, and shared-resource
capacity/exclusivity. Unsupported domain fields require an explicit future API
contract change.

## Execution and snapshots

DecisionPipelineService composes the existing engines in order: feasibility,
portfolio effects, commercial evaluation, scoring, planner, cash flow, and
final validation. API handlers contain no decision logic.

Every run stores:

- the complete effective input;
- V1 assumption version and values;
- every phase result;
- final plan, cash flow, and decision;
- run/scenario IDs, timestamp, status, and safe error metadata.

These JSON snapshots are immutable. Editing or deleting a scenario does not
alter its historical runs.

## Comparison

Comparison reports status transitions, selected/delayed/NO_BID additions and
removals, capacity deltas, expected/downside/minimum cash deltas, buffer-breach
change, and major risk/strength changes. It intentionally does not label either
run as better.

## Persistence and errors

The default store is runtime/scenarios.sqlite3, ignored by Git. Set
NEXAWORKS_DB_PATH to choose another SQLite file. Tests inject a temporary,
isolated database and verify re-instantiation.

Errors use HTTP 400 for invalid overrides, 404 for missing scenarios/runs, 409
for invalid run state, 422 for request-model validation, and a generic 500 for
unexpected pipeline failures. Server stack traces are never returned.

## Limitations

- Execution is synchronous; no background workers or WebSockets are included.
- SQLite targets one application instance; distributed locking and migration
  tooling are outside Phase 4.
- Authentication and authorization are not implemented.
- Overrides expose a safe subset of current domain fields rather than arbitrary
  JSON patching.
- Run comparison is descriptive and does not create a new ranking rule.
