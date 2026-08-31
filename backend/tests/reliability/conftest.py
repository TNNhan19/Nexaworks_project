from __future__ import annotations

import pytest

from app.domain.models import ResourceRequirement, SkillRequirement

from .factories import (
    make_dataset,
    make_effect,
    make_option,
    make_person,
    make_resource,
    make_work_item,
)


@pytest.fixture
def unseen_dataset():
    people = [
        make_person("ALICE_X", capacity=30, skills={"robotics": 3}, languages=["FR"]),
        make_person("BOB_Y", capacity=30, skills={"legal_review": 2}, languages=["EN"]),
    ]
    resource = make_resource("GPU_CLUSTER", capacity=10, exclusive=True)
    trigger = make_work_item("TRIGGER_TASK", hours=2, mandatory=True)
    delivery = make_work_item(
        "ALPHA_TASK",
        hours=4,
        mandatory=True,
        dependencies=["TRIGGER_TASK"],
        skills=[
            SkillRequirement(skill="robotics", min_level=3),
            SkillRequirement(skill="legal_review", min_level=2),
        ],
        languages=["FR"],
        resources=[ResourceRequirement(resource_id="GPU_CLUSTER", hours=2)],
        revenue=2_000,
        direct_cost=200,
        committed=True,
        cash_in_days=0,
    )
    opportunity = make_work_item(
        "CLIENT_EXPANSION",
        hours=1,
        work_type="sales_opportunity",
    )
    option = make_option(
        "CLIENT_EXPANSION",
        "PREMIUM_OFFER",
        price=5_000,
        cost=500,
        delivery_hours=2,
        probability=1,
        payment_days=0,
        dependencies=["TRIGGER_TASK"],
    )
    effects = [
        make_effect(
            "UNLOCK_PREMIUM",
            trigger="TRIGGER_TASK",
            targets=["PREMIUM_OFFER"],
            effect_type="commercial_option_unlock",
        ),
        make_effect(
            "BONUS_CASH",
            trigger="ALPHA_TASK",
            targets=["company_cash"],
            effect_type="cash_inflow",
            value_jpy=700,
            probability=0.5,
        ),
    ]
    return make_dataset(
        people=people,
        work_items=[trigger, delivery, opportunity],
        resources=[resource],
        options=[option],
        effects=effects,
        starting_cash=10_000,
        fixed_outflow=1_003,
        minimum_buffer=1_000,
    )
