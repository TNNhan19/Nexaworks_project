from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScoringWeights(BaseModel):
    """V1 BALANCED scoring weights (modeling assumptions, not dataset facts)."""

    model_config = ConfigDict(frozen=True)

    economic_value: float = Field(default=0.30, ge=0)
    strategic_customer: float = Field(default=0.20, ge=0)
    urgency_cost_of_delay: float = Field(default=0.15, ge=0)
    cash_timing: float = Field(default=0.10, ge=0)
    follow_on_value: float = Field(default=0.10, ge=0)
    capacity_efficiency: float = Field(default=0.10, ge=0)
    risk_resilience: float = Field(default=0.05, ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "ScoringWeights":
        total = sum(self.model_dump().values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"scoring weights must sum to 1.0; got {total}")
        return self


class AssumptionRegistry(BaseModel):
    """Explicit modeling decisions that the assignment intentionally leaves open.

    Keeping them in one object makes scenario comparison and interview changes
    reproducible instead of hiding assumptions throughout the codebase.
    """

    model_config = ConfigDict(frozen=True)

    planning_granularity: Literal["day"] = "day"
    work_effort_interpretation: Literal["total_person_hours"] = "total_person_hours"
    skill_coverage_policy: Literal["team_coverage"] = "team_coverage"
    language_coverage_policy: Literal["customer_facing_coverage"] = "customer_facing_coverage"
    sales_capacity_policy: Literal["full_if_committed"] = "full_if_committed"
    dependency_policy: Literal["hard"] = "hard"
    contract_internal_deadline_policy: Literal["soft_with_penalty"] = "soft_with_penalty"
    sales_opportunity_deadline_policy: Literal["hard_or_expiry"] = "hard_or_expiry"
    mandatory_policy: Literal["required_target"] = "required_target"
    direct_cost_timing: Literal["prorated_over_execution"] = "prorated_over_execution"
    commercial_option_policy: Literal["mutually_exclusive"] = "mutually_exclusive"
    probabilistic_effect_policy: Literal["expected_value_plus_downside"] = (
        "expected_value_plus_downside"
    )
    hours_reduction_combination_policy: Literal["multiplicative_compounding"] = (
        "multiplicative_compounding"
    )
    # Multiple active deterministic reductions compound from canonical base hours.

    scoring_profile: Literal["balanced_v1"] = "balanced_v1"
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    scoring_quality_risk_resilience: float = Field(default=0.5, ge=0, le=1)

    # --- Phase 2E planning assumptions -----------------------------------------
    # The source data supplies horizon-level capacity and date-only unavailability,
    # but no daily shifts or intra-day resource clock. Keep the conservative V1
    # interpretations explicit and scenario-configurable.
    daily_capacity_policy: Literal["even_distribution_over_available_days"] = (
        "even_distribution_over_available_days"
    )
    unavailable_range_boundary_policy: Literal["inclusive"] = "inclusive"
    exclusive_resource_day_policy: Literal[
        "one_active_work_item_per_resource_per_day"
    ] = "one_active_work_item_per_resource_per_day"
    commercial_delivery_timing_policy: Literal["reserved_capacity"] = (
        "reserved_capacity"
    )

    # --- Language coverage configuration -----------------------------------------
    # CUSTOMER_FACING_COVERAGE policy: to count as eligible for a required language,
    # a person must speak the language AND (if language_customer_facing_skill is set)
    # have that skill at or above language_customer_facing_min_level.
    #
    # Default (language_customer_facing_skill=None): any speaker qualifies.
    # Example override: skill="project_management", min_level=3 → only people with
    # project_management >= 3 count as customer-facing language coverage.
    language_customer_facing_skill: str | None = Field(
        default=None,
        description=(
            "If set, only people with this skill >= language_customer_facing_min_level "
            "are counted as customer-facing for language coverage purposes. "
            "None means any speaker of the required language qualifies."
        ),
    )
    language_customer_facing_min_level: float = Field(
        default=0.0,
        ge=0,
        description=(
            "Minimum level of language_customer_facing_skill required for a person "
            "to be counted as customer-facing. Only used when "
            "language_customer_facing_skill is not None."
        ),
    )


DEFAULT_ASSUMPTIONS = AssumptionRegistry()
