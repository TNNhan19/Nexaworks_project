# Feasibility Engine — Phase 2A

> **Status:** Implemented (Phase 2A complete)
> **Part of:** NexaWorks Decision Support System — Decision Engine pipeline, Step 7

---

## 1. Purpose

The Feasibility Engine answers a single question:

> *"For a given work item or candidate action, is it operationally feasible under the current dataset and assumptions — and if not, exactly why?"*

The output is **structured and machine-readable**, not user-facing natural-language text.  The frontend uses `react-i18next` to translate reason codes into JA / EN / VI.

---

## 2. Architecture

```
CandidateDataset (validated domain model)
         +
AssumptionRegistry
         ↓
┌─────────────────────────────────────────────┐
│            FeasibilityEngine                │
│                                             │
│  skill_checker.py    → TEAM_COVERAGE        │
│  language_checker.py → CUSTOMER_FACING      │
│  dependency_checker.py → HARD policy        │
│  capacity_checker.py → TOTAL_PERSON_HOURS   │
│  resource_checker.py → structural ceiling   │
│  deadline_checker.py → SOFT/HARD_OR_EXPIRY  │
└────────────────┬────────────────────────────┘
                 ↓
         FeasibilityResult
   status: FEASIBLE | BLOCKED | INFEASIBLE
   hard_failures / blockers / warnings
   (all machine-readable reason codes + evidence)
```

The engine has **zero dependency on FastAPI or any web framework**.  The API (`app/api/feasibility.py`) is a thin adapter only.

---

## 3. Status Semantics

| Status | Meaning |
|---|---|
| **FEASIBLE** | No hard constraints violated, no active blockers |
| **BLOCKED** | No permanent hard failures, but blockers exist (e.g. unsatisfied HARD dependency) that the Planner may resolve |
| **INFEASIBLE** | One or more permanent hard constraint violations exist |

Warnings may coexist with any status.

### Status determination rule

```
if hard_failures:
    status = INFEASIBLE
elif blockers:
    status = BLOCKED
else:
    status = FEASIBLE
```

---

## 4. Rules Implemented

### 4.1 Skill Coverage — `TEAM_COVERAGE`

- Each `required_skill` must be met by **at least one individual person** at or above the `min_level` threshold.
- Skill levels are **never summed** across people for the same skill.
- Different skills may be covered by different team members.

```
AI=3 + AI=3  ≠  AI=6     ← INVALID
AI=3 by Person A; PM=4 by Person B  → both skills covered  ← VALID
```

### 4.2 Language Coverage — `CUSTOMER_FACING_COVERAGE`

- Not every technical contributor must speak the required language.
- "Customer-facing" is **configurable** via `AssumptionRegistry`:
  - `language_customer_facing_skill = None` (default): any speaker qualifies.
  - `language_customer_facing_skill = "project_management"` + `language_customer_facing_min_level = 3`: only people with PM ≥ 3 AND the language qualify.
- Language coverage results are **separate** from skill coverage results.

### 4.3 Dependency Handling — `HARD` policy + BLOCKED distinction

| Condition | Result |
|---|---|
| All deps in `completed_ids` | `DependencyResult.satisfied = True` |
| Dep exists in dataset, not in `completed_ids` | BLOCKER (`DEPENDENCY_NOT_SATISFIED`) → status **BLOCKED** |

> **Key design:** an unsatisfied HARD dependency is **BLOCKED, not INFEASIBLE**.  The Planner (Phase 2E) may schedule the prerequisite first within the same planning horizon.

### 4.4 Person Capacity — `TOTAL_PERSON_HOURS`

- `required_hours` is a **shared pool** — divided across all assignees.
- Capacity pool is the **entire team** — not restricted to skill/language-eligible people.
- Skill coverage and hour capacity are **orthogonal** concerns.
- If total team capacity < required_hours → hard failure (`INSUFFICIENT_PERSON_CAPACITY`).

### 4.5 Shared Resources — Structural Check

- For each `ResourceRequirement`: checks `required_hours ≤ resource.capacity_hours`.
- `exclusive = true` resources are noted; scheduling conflict detection requires the Planner.
- Exceeding ceiling → hard failure (`RESOURCE_CAPACITY_EXCEEDED`).

### 4.6 Deadline Policy

| Work item type | Policy | Expired behavior |
|---|---|---|
| `delivery`, `incident`, `internal` | `SOFT_WITH_PENALTY` | WARNING (`DEADLINE_AT_RISK`) |
| `sales_opportunity` | `HARD_OR_EXPIRY` | Hard failure (`OPPORTUNITY_EXPIRED`) → INFEASIBLE |

Deadline status classification:

| Condition | Status |
|---|---|
| `due_date < planning_date` | `EXPIRED` |
| `planning_date ≤ due_date ≤ planning_end` | `WITHIN_HORIZON` |
| `due_date > planning_end` | `OUTSIDE_HORIZON` |

> **Important:** `DEADLINE_AT_RISK` is **not** emitted merely because a due date is within the horizon when no actual schedule exists.  Schedule-based lateness belongs to the Planner (Phase 2E).

### 4.7 Mandatory Items — `REQUIRED_TARGET`

- `mandatory = true` does **NOT** override hard constraint failures.
- If a mandatory item is INFEASIBLE → adds `MANDATORY_ITEM_INFEASIBLE` **warning**.
- If a mandatory item is BLOCKED → adds `MANDATORY_ITEM_BLOCKED` **warning**.

---

## 5. Result Structure

```json
{
  "work_item_id": "W001",
  "status": "BLOCKED",

  "skill_coverage": [
    {
      "skill": "ai",
      "required_level": 4,
      "covered": true,
      "eligible_people": ["P002", "P004"],
      "best_available_level": 5.0
    }
  ],

  "language_coverage": [
    {
      "language": "ja",
      "covered": true,
      "eligible_people": ["P001", "P003", "P005", "P007"]
    }
  ],

  "dependencies": {
    "satisfied": false,
    "required": ["W005"],
    "missing": ["W005"]
  },

  "capacity": {
    "required_hours": 210.0,
    "total_team_capacity_hours": 748.0,
    "sufficient": true,
    "note": "Capacity pool: all people in dataset. Skill/language coverage is evaluated separately."
  },

  "resources": [
    {
      "resource_id": "R001",
      "required_hours": 45.0,
      "max_capacity_hours": 128.0,
      "sufficient": true,
      "exclusive": true
    }
  ],

  "deadline": {
    "policy": "SOFT_WITH_PENALTY",
    "status": "WITHIN_HORIZON",
    "due_date": "2026-10-25",
    "planning_date": "2026-10-05",
    "planning_end": "2026-11-01",
    "days_until_due": 20
  },

  "hard_failures": [],

  "blockers": [
    {
      "code": "DEPENDENCY_NOT_SATISFIED",
      "severity": "WARNING",
      "work_item_id": "W001",
      "details": {
        "dependency_id": "W005",
        "dependency_exists_in_dataset": true,
        "policy": "HARD"
      }
    }
  ],

  "warnings": [
    {
      "code": "MANDATORY_ITEM_BLOCKED",
      "severity": "WARNING",
      "work_item_id": "W001",
      "details": {
        "mandatory": true,
        "status": "BLOCKED"
      }
    }
  ]
}
```

---

## 6. Reason Codes

All codes are in `reason_codes.py`.  The frontend translates them.

| Code | Severity | Contributes To |
|---|---|---|
| `MISSING_SKILL_COVERAGE` | ERROR | hard_failures → INFEASIBLE |
| `MISSING_LANGUAGE_COVERAGE` | ERROR | hard_failures → INFEASIBLE |
| `INSUFFICIENT_PERSON_CAPACITY` | ERROR | hard_failures → INFEASIBLE |
| `OPPORTUNITY_EXPIRED` | ERROR | hard_failures → INFEASIBLE |
| `RESOURCE_CAPACITY_EXCEEDED` | ERROR | hard_failures → INFEASIBLE |
| `RESOURCE_UNAVAILABLE` | ERROR | hard_failures → INFEASIBLE |
| `DEPENDENCY_NOT_SATISFIED` | WARNING | blockers → BLOCKED |
| `MANDATORY_ITEM_INFEASIBLE` | WARNING | warnings (informational) |
| `MANDATORY_ITEM_BLOCKED` | WARNING | warnings (informational) |
| `DEADLINE_AT_RISK` | WARNING | warnings (soft deadline expired) |
| `COMMERCIAL_OPTION_LOCKED` | — | stub (Phase 2C) |
| `COMMERCIAL_OPTION_CONFLICT` | — | stub (Phase 2C) |

---

## 7. Feasibility vs Scoring

> **Hard operational constraints are NEVER converted into score penalties.**

```
Required AI >= 4, no eligible employee:
  WRONG:  priority_score -= 30
  CORRECT: feasible=INFEASIBLE, reason=MISSING_SKILL_COVERAGE
```

Scoring (Phase 2D) operates only on choices that are already operationally possible.

---

## 8. Assumptions Used

All assumptions come from `AssumptionRegistry` (no hard-coded policies):

| Policy | Field | Default |
|---|---|---|
| Skill coverage | `skill_coverage_policy` | `team_coverage` |
| Work effort | `work_effort_interpretation` | `total_person_hours` |
| Language | `language_coverage_policy` | `customer_facing_coverage` |
| Language eligibility proxy skill | `language_customer_facing_skill` | `None` (any speaker) |
| Language proxy min level | `language_customer_facing_min_level` | `0.0` |
| Dependencies | `dependency_policy` | `hard` |
| Contract/internal deadline | `contract_internal_deadline_policy` | `soft_with_penalty` |
| Sales deadline | `sales_opportunity_deadline_policy` | `hard_or_expiry` |
| Mandatory | `mandatory_policy` | `required_target` |

---

## 9. API Endpoints (Development)

| Endpoint | Description |
|---|---|
| `GET /api/v1/feasibility` | Feasibility for all work items |
| `GET /api/v1/feasibility/{work_item_id}` | Feasibility for a single item |

> These are development/analysis endpoints.  The engine itself has no dependency on FastAPI.

---

## 10. Known Limitations

| Limitation | Where Resolved |
|---|---|
| Capacity check uses total team hours (structural), not per-person schedule | Phase 2E (Planner) |
| No schedule-based resource conflict detection for exclusive resources | Phase 2E (Planner) |
| `DEADLINE_AT_RISK` not raised for within-horizon items without schedule | Phase 2E (Planner) |
| Portfolio effects not applied before feasibility check | Phase 2B (Portfolio Effects) |
| Commercial option unlock/lock conditions not fully evaluated | Phase 2C (Commercial Evaluation) |
| Late penalty cash impact not computed | Phase 2F (Cash-flow Simulator) |

---

## 11. What Is Intentionally Deferred

- **Phase 2B** — Portfolio effect application (hours_reduction, commercial_option_unlock, etc.)
- **Phase 2C** — Commercial option evaluation and unlock checks
- **Phase 2D** — Value / priority scoring (only for feasible/blocked items)
- **Phase 2E** — Heuristic planner (person assignment, daily scheduling, schedule-based conflict)
- **Phase 2F** — Cash-flow simulation (PRORATED_OVER_EXECUTION cost timing)
- **Phase 2G** — Final feasibility recheck after full plan is generated

---

## 12. Module Structure

```
backend/app/decision_engine/feasibility/
├── __init__.py          # public exports
├── engine.py            # FeasibilityEngine orchestrator
├── models.py            # Pydantic result types
├── reason_codes.py      # Enums: FeasibilityStatus, ReasonCode, Severity, DeadlinePolicy, DeadlineStatus
├── skill_checker.py     # TEAM_COVERAGE implementation
├── language_checker.py  # CUSTOMER_FACING_COVERAGE implementation
├── dependency_checker.py # HARD policy, BLOCKED distinction
├── capacity_checker.py  # TOTAL_PERSON_HOURS, full team pool
├── resource_checker.py  # Structural hours-vs-ceiling check
└── deadline_checker.py  # EXPIRED/WITHIN_HORIZON/OUTSIDE_HORIZON classification
```
