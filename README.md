# NexaWorks Decision Support System

Starter implementation for the four-week NexaWorks management decision challenge.

## Current milestone -- Phase 2G: Final Validation + Explanation

### Phase 1 (complete)

- Canonical JSON + JSON Schema included under `data/`
- Flexible Pydantic domain models (unknown fields preserved)
- JSON Schema validation + semantic reference validation
- Central Assumption Registry containing all V1 policies
- Baseline summary service
- Minimal FastAPI endpoints
- Unit tests against the canonical dataset

### Phase 2A (complete) -- Feasibility Engine

- `backend/app/decision_engine/feasibility/` -- pure Python engine, no FastAPI dependency
  - `skill_checker.py` -- TEAM_COVERAGE (levels never summed)
  - `language_checker.py` -- CUSTOMER_FACING_COVERAGE (configurable via AssumptionRegistry)
  - `dependency_checker.py` -- HARD policy; unsatisfied deps -> BLOCKED (not INFEASIBLE)
  - `capacity_checker.py` -- TOTAL_PERSON_HOURS; full team pool, orthogonal to skill coverage
  - `resource_checker.py` -- structural hours-vs-ceiling check, exclusive flag noted
  - `deadline_checker.py` -- EXPIRED/WITHIN_HORIZON/OUTSIDE_HORIZON; SOFT_WITH_PENALTY vs HARD_OR_EXPIRY
  - `engine.py` -- orchestrator; FEASIBLE / BLOCKED / INFEASIBLE status with hard_failures / blockers / warnings
- API endpoints: `GET /api/v1/feasibility` and `GET /api/v1/feasibility/{work_item_id}`
- 45 automated tests (all passing)
- `docs/FEASIBILITY_ENGINE.md` -- full engine documentation

### Phase 2B (complete) -- Portfolio Effects Engine

- `backend/app/decision_engine/portfolio/` -- pure Python engine, no FastAPI dependency
  - `context.py` -- PortfolioEvaluationContext (immutable, deterministic)
  - `reason_codes.py` -- PortfolioEffectCode enum (no localized strings)
  - `models.py` -- PortfolioEffectsResult, DerivedWorkItemState, CashEffect, etc.
  - `engine.py` -- PortfolioEffectsEngine orchestrator; generic dispatch on effect.type
  - `handlers/quality_prerequisite.py` -- qualitative risk flag only; no hard dependency created
  - `handlers/hours_reduction.py` -- deterministic; always derived from base hours (idempotent)
  - `handlers/future_hours_reduction.py` -- probabilistic; success/downside both preserved
  - `handlers/commercial_option_unlock.py` -- HARD availability gate; no ranking/selection
  - `handlers/cash_inflow.py` -- probabilistic; expected/success/downside all separated
- API endpoint: `GET /api/v1/portfolio`
- 39 new automated tests (84 total, all passing)
- `docs/PORTFOLIO_EFFECTS.md` -- full engine documentation
- Feasibility Engine updated: optional `effective_hours_override` parameter (backward compatible)

### Phase 2C (complete) -- Commercial Evaluation

- `backend/app/decision_engine/commercial/` -- deterministic option facts and validation
- Phase 2B option availability and Phase 2A deliverability/deadline semantics are composed, not duplicated
- Gross margin, expected value, follow-on value, full committed hours, and cash timing facts remain separate
- Canonical commercial options only; no inferred/synthetic `NO_BID`, score, ranking, recommendation, or planner
- API endpoints: `GET /api/v1/commercial` and `GET /api/v1/commercial/{work_item_id}`
- `docs/COMMERCIAL_EVALUATION.md` -- Phase 2C contract and limitations

### Phase 2D (complete) -- Value / Priority Scoring

- `backend/app/decision_engine/scoring/` -- deterministic 0–100 business-value scoring
- Explicit BALANCED V1 weights with validation and visible contribution traces
- Reusable empirical-CDF `ScoringReference` for scenario-comparable normalization
- N/A-aware effective-weight renormalization
- Eligibility remains separate from score; locks/blockers/infeasibility are never penalties
- Canonical `DO_WORK_ITEM` / `SELECT_OPTION` actions only; no synthetic NO_BID
- API endpoints: `GET /api/v1/scoring` and `GET /api/v1/scoring/{action_id}`
- `docs/SCORING.md` -- formulas, sources, reference, and limitations

### Phase 2E (complete) -- Heuristic Planner

- Transitive dependency/unlock closure with cycle detection and dynamic completion context
- Mandatory-first, score-ordered deterministic selection with transactional rollback
- Canonical option exclusivity and planner-level `NO_BID`; no label/value inference
- TEAM_COVERAGE assignment, even daily capacity, unavailable dates, and day scheduling
- Full commercial delivery hours represented as reserved capacity
- Exclusive shared-resource day scheduling and horizon-capacity enforcement
- API endpoints: `GET /api/v1/plan` and `POST /api/v1/plan`
- `docs/PLANNER.md` -- heuristic, assumptions, result contract, and limitations

### Phase 2F (complete) -- Cash-Flow Simulator

- Independent EXPECTED, DOWNSIDE, and SUCCESS daily cash ledgers
- Exact integer-JPY proration and reconciliation
- Fixed outflow, work costs/receipts, selected-option conditional cash, and E005
- Outside-horizon future events separated from current cash
- Minimum-buffer and negative-cash detection with structured evidence
- API endpoint: POST /api/v1/cash-flow
- docs/CASH_FLOW.md -- event timing, scenario rules, assumptions, and limitations

### Phase 2G (complete) -- Final Validation + Explanation

- `backend/app/decision_engine/final_validation/` -- pure Python engine, no FastAPI dependency
  - `reason_codes.py` -- OperationalStatus, FinancialStatus, OverallStatus, ExplanationCode, SourcePhase
  - `models.py` -- FinalDecisionResult, ExplanationRecord, DecisionExplanation, MandatorySummary, etc.
  - `validators.py` -- read-only structural validation functions; never mutate upstream results
  - `explainer.py` -- per-decision explanation builder; CashSummary builder; CASH_TIMING_MISMATCH detection
  - `engine.py` -- FinalValidationEngine.validate() orchestrator; status propagation rules
- API endpoint: `POST /api/v1/final-decision`
- 258 total automated tests (all passing), including 39 Phase 2G tests
- `docs/FINAL_VALIDATION.md` -- dimensional statuses, validation rules, provenance, no-replanning principle
- Canonical result: `PLAN_AT_RISK` (operationally partial + financially NEGATIVE_CASH)

## Run

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open API docs at `http://127.0.0.1:8000/docs`.

Useful endpoints:

- `GET /health`
- `GET /api/v1/assumptions`
- `GET /api/v1/dataset/summary`
- `GET /api/v1/feasibility`
- `GET /api/v1/feasibility/{work_item_id}`
- `GET /api/v1/portfolio`
- `GET /api/v1/commercial`
- `GET /api/v1/commercial/{work_item_id}`
- `GET /api/v1/scoring`
- `GET /api/v1/scoring/{action_id}`
- `GET /api/v1/plan` / `POST /api/v1/plan`
- `POST /api/v1/cash-flow`
- `POST /api/v1/final-decision`

## Test

```bash
cd backend
pytest -q
```

258 tests, 0 failures (as of Phase 2G).

## Canonical Dataset Phase 2A Feasibility Results

```
Total work items : 24
  FEASIBLE       : 21
  BLOCKED        : 3   (W001, W006, W007 -- all waiting on W005)
  INFEASIBLE     : 0

Mandatory items  : 6
  FEASIBLE       : 5
  BLOCKED        : 1   (W001 -- mandatory delivery, blocked by W005)
  INFEASIBLE     : 0

Team capacity    : 748h
Total workload   : 1277h (171% of capacity)
```

> **Important:** BASE FEASIBILITY only. 21 feasible items cannot run simultaneously. The Planner (Phase 2E) selects a subset within capacity constraints.

## Canonical Dataset Phase 2B Portfolio Effects (base scenario -- no triggers satisfied)

```
E001  quality_prerequisite      W005 -> W001,W006,W007  ELEVATED RISK (qualitative)
E002  hours_reduction           W013 -> W015            68.0h base (51.0h if W013 done)
E003  future_hours_reduction    W017 -> W010,W019       p=0.75, 20% if W017 succeeds
E004  commercial_option_unlock  W022 -> W007-B          LOCKED (COMMERCIAL_OPTION_LOCKED)
E005  cash_inflow               W021 -> company_cash    p=0.85, +3.8M JPY if W021 done
```

> **Important:** Portfolio effects evaluation only. Not a final business recommendation. Scoring and planning are deferred to Phase 2D-2E.

## Canonical Dataset Phase 2G Final Decision

```
Overall status      : PLAN_AT_RISK
Operational status  : OPERATIONALLY_PARTIAL
Financial status    : NEGATIVE_CASH

Selected            : 10 actions
Delayed             : 9 actions
NO-BID              : 6 opportunities
Mandatory           : 6/6 scheduled (0 infeasible)

Capacity used       : 737/748 hrs (98.5%)

EXPECTED ending cash: JPY -700,000   (buffer breach 2026-10-21, 12 days)
DOWNSIDE ending cash: JPY -3,930,000 (buffer breach 2026-10-17, 16 days)
SUCCESS ending cash : JPY -130,000   (buffer breach 2026-10-22, 11 days)

Future receipts (outside horizon):
  W001  2026-11-21  JPY 18,000,000
  W002  2026-11-27  JPY  4,200,000
  W012-A 2027-01-08 JPY  5,400,000

Main risks    : NEGATIVE_CASH_EXPECTED, CASH_BUFFER_BREACH, CASH_TIMING_MISMATCH
Main strengths: MANDATORY_WORK_SCHEDULED, PERSON_CAPACITY_VALID
```

> Structurally solvent (JPY 27.6M future receipts) but a timing gap causes
> negative in-horizon cash across all scenarios. No code changes required —
> this is the correct Phase 2G validated result.
