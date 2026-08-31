# Heuristic Planner — Phase 2E

## Boundary

Phase 2E builds a deterministic four-week operational plan: decisions, prerequisite closure, assignments, day-level person schedule, resource schedule, and commercial delivery reservations. It does not simulate cash or claim cash safety.

> Phase 2E produces the operational plan. Phase 2F must still validate cash-flow and minimum cash buffer.

## Inputs and source ownership

- Canonical/domain data owns dependencies, skills, languages, dates, people, resources, mandatory flags, and option declarations.
- Phase 2A owns structural feasibility, coverage, dependency, and deadline semantics.
- Phase 2B owns effective deterministic hours, portfolio warnings, and unlock state.
- Phase 2C owns option availability, commercial facts, and full delivery commitment.
- Phase 2D score is a soft ordering signal only. It never overrides a hard constraint.

The Planner does not rely on the scoring payload alone. It dynamically rebuilds Phase 2B/2C context from canonical values as scheduled prerequisites complete.

## Deterministic heuristic

1. Load caller-supplied completed work.
2. Sort mandatory targets by due date and ID.
3. Resolve transitive dependency/unlock closure and detect cycles.
4. Schedule prerequisites before dependents, then mandatory targets.
5. Re-evaluate deterministic portfolio effects from canonical base data.
6. Sort optional action candidates by score descending, due date ascending, action ID ascending.
7. Transactionally try each target plus missing closure. Roll back the whole attempt when it cannot fit.
8. Enforce person capacity, coverage, dates, expiry, resource capacity/exclusivity, and commercial mutual exclusion.
9. Emit `DELAY` for unselected work and planner-level `NO_BID` for an opportunity with no selected canonical option.

`BLOCKED` and `LOCKED` are current-context states, not permanent rejection. Completion of a prerequisite updates the completed context. Canonically, W005 can unblock W001/W006/W007 and W022 can unlock W007-B.

## Assignment and capacity assumptions

The source supplies `Person.capacity_hours` for the full horizon and date ranges in `unavailable_ranges`; it has no daily shift field. V1 therefore registers:

```text
DAILY_CAPACITY_POLICY = EVEN_DISTRIBUTION_OVER_AVAILABLE_DAYS
UNAVAILABLE_RANGE_BOUNDARY_POLICY = INCLUSIVE
```

For each person, the inclusive planning dates minus inclusive unavailable dates are available days. Daily capacity is `capacity_hours / available_days`; unavailable dates have zero. Both daily and horizon totals are enforced. No eight-hour day is invented.

`TEAM_COVERAGE` remains unchanged: different assigned people may cover different skills, levels are not summed, and every coverage witness receives positive work allocation. `CUSTOMER_FACING_COVERAGE` is read from `AssumptionRegistry`.

## Day scheduling and deadlines

Scheduling granularity is `DAY`; allocation uses earliest feasible date first. `earliest_start`, unavailability, daily capacity, and horizon end are hard. A dependent starts strictly after prerequisite completion.

- Sales-opportunity base effort must complete by its `HARD_OR_EXPIRY` due date.
- Other work uses `SOFT_WITH_PENALTY`; lateness produces `SCHEDULED_AFTER_DUE_DATE`, late days, and declared daily penalty evidence.

## Shared resources

The schema supplies horizon resource hours and `exclusive`, but no daily rate or intra-day clock. V1 uses:

```text
EXCLUSIVE_RESOURCE_DAY_POLICY = ONE_ACTIVE_WORK_ITEM_PER_RESOURCE_PER_DAY
```

Resource requirements are distributed across the action's active dates for traceability. Total resource capacity is enforced, and an exclusive resource cannot be assigned to two actions on the same date.

## Commercial decisions and delivery

At most one canonical option is selected per opportunity. `NO_BID` is a Planner decision, never a synthetic option and never inferred from label or zero values. W011-C/W012-B remain ordinary canonical options.

The option's base opportunity effort is scheduled. Phase 2C full `committed_delivery_hours_if_won` is reserved without probability reduction. Because the source has no delivery calendar, those entries are typed `RESERVED_DELIVERY`, not confirmed execution dates. Parent resource requirements apply to base opportunity effort; the option schema declares no delivery-resource facts.

## Result and API

`PlanResult` contains structured decisions, closures, assignments, person schedule, resource schedule, selected/delayed/no-bid sets, mandatory failures, capacity summaries, blockers, warnings, and active assumptions.

- `GET /api/v1/plan` runs the canonical baseline.
- `POST /api/v1/plan` accepts `completed_work_item_ids`.

The core Planner is independent of FastAPI.

## Limitations

- Greedy V1 is deterministic but not globally optimal.
- Calendar dates are treated as planning days because no workweek/holiday calendar exists.
- Resource-hour distribution has no intra-day meaning.
- Reserved commercial delivery capacity is not a confirmed delivery schedule.
- Probabilistic effects are never randomly realized or treated as guaranteed capacity reductions.
- Cash feasibility and minimum-buffer validation belong to Phase 2F.
