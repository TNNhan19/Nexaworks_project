"""Resource checker — shared resource feasibility.

Business rule:
- Resources marked exclusive cannot be double-booked.
- required_hours for each resource must not exceed the resource's capacity ceiling.

Phase 2A scope (before the Planner exists):
    Structural check: required_hours vs max capacity_hours.
    If required_hours > capacity_hours → RESOURCE_CAPACITY_EXCEEDED (hard failure).
    If resource is exclusive → noted in result; scheduling conflict detection
    requires the Planner's daily schedule (Phase 2E) and is NOT attempted here.

We deliberately do NOT simulate a daily schedule that does not yet exist.
"""
from __future__ import annotations

from app.domain.models import ResourceRequirement, SharedResource

from .models import ReasonItem, ResourceResult
from .reason_codes import ReasonCode, Severity


def check_resources(
    work_item_id: str,
    resource_requirements: list[ResourceRequirement],
    shared_resources: list[SharedResource],
) -> tuple[list[ResourceResult], list[ReasonItem]]:
    """Evaluate resource requirements against resource capacity ceilings.

    Parameters
    ----------
    work_item_id:
        ID of the work item being evaluated.
    resource_requirements:
        Resource requirements from the work item.
    shared_resources:
        All shared resources in the dataset.

    Returns
    -------
    results:
        One ``ResourceResult`` per resource requirement.
    failures:
        Hard failures for capacity exceeded or unavailable resources.
    """
    resource_map: dict[str, SharedResource] = {r.id: r for r in shared_resources}
    results: list[ResourceResult] = []
    failures: list[ReasonItem] = []

    for req in resource_requirements:
        resource = resource_map.get(req.resource_id)

        if resource is None:
            # Should have been caught by schema/reference validation, but guard anyway
            failures.append(
                ReasonItem(
                    code=ReasonCode.RESOURCE_UNAVAILABLE,
                    severity=Severity.ERROR,
                    work_item_id=work_item_id,
                    details={"resource_id": req.resource_id},
                )
            )
            continue

        sufficient = req.hours <= resource.capacity_hours
        exclusive = bool(resource.exclusive)

        results.append(
            ResourceResult(
                resource_id=req.resource_id,
                required_hours=req.hours,
                max_capacity_hours=resource.capacity_hours,
                sufficient=sufficient,
                exclusive=exclusive,
            )
        )

        if not sufficient:
            failures.append(
                ReasonItem(
                    code=ReasonCode.RESOURCE_CAPACITY_EXCEEDED,
                    severity=Severity.ERROR,
                    work_item_id=work_item_id,
                    details={
                        "resource_id": req.resource_id,
                        "required_hours": req.hours,
                        "max_capacity_hours": resource.capacity_hours,
                        "excess_hours": req.hours - resource.capacity_hours,
                        "exclusive": exclusive,
                    },
                )
            )

    return results, failures
