from app.decision_engine.assumptions import DEFAULT_ASSUMPTIONS


def test_locked_modeling_assumptions() -> None:
    a = DEFAULT_ASSUMPTIONS
    assert a.skill_coverage_policy == "team_coverage"
    assert a.work_effort_interpretation == "total_person_hours"
    assert a.language_coverage_policy == "customer_facing_coverage"
    assert a.sales_capacity_policy == "full_if_committed"
    assert a.dependency_policy == "hard"
    assert a.contract_internal_deadline_policy == "soft_with_penalty"
    assert a.sales_opportunity_deadline_policy == "hard_or_expiry"
    assert a.direct_cost_timing == "prorated_over_execution"
    assert a.probabilistic_effect_policy == "expected_value_plus_downside"
