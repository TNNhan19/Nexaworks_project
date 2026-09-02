"""Small same-schema factories for Phase 3 reliability tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.decision_engine.cash_flow import CashFlowResult, CashFlowSimulator
from app.decision_engine.commercial import CommercialEvaluationEngine, CommercialEvaluationResult
from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityResult
from app.decision_engine.final_validation import FinalDecisionResult, FinalValidationEngine
from app.decision_engine.planner import PlanResult, PlannerEngine
from app.decision_engine.portfolio import PortfolioEffectsEngine, PortfolioEffectsResult
from app.decision_engine.scoring import ScoringEngine, ScoringReference, ScoringResult
from app.domain.models import (
    CandidateDataset,
    CommercialOption,
    Company,
    Customer,
    DateRange,
    Enumerations,
    Metadata,
    Person,
    PortfolioEffect,
    ResourceRequirement,
    SharedResource,
    SkillRequirement,
    WorkItem,
)

PLAN_START = date(2027, 3, 1)
PLAN_END = date(2027, 3, 7)


def make_person(
    person_id: str = "EMP_ALPHA",
    *,
    capacity: float = 40,
    skills: dict[str, float] | None = None,
    languages: list[str] | None = None,
    unavailable: list[DateRange] | None = None,
) -> Person:
    return Person(
        id=person_id,
        name=person_id,
        capacity_hours=capacity,
        hourly_cost_jpy=1_000,
        skills={"general": 5} if skills is None else skills,
        languages=["EN"] if languages is None else languages,
        unavailable_ranges=[] if unavailable is None else unavailable,
    )


def make_customer(customer_id: str = "CLIENT_X") -> Customer:
    return Customer(
        id=customer_id,
        name=customer_id,
        strategic_value=3,
        payment_reliability=0.8,
        default_payment_days=30,
    )


def make_resource(
    resource_id: str = "RESOURCE_GPU_X",
    *,
    capacity: float = 40,
    exclusive: bool = False,
) -> SharedResource:
    return SharedResource(
        id=resource_id,
        name=resource_id,
        capacity_hours=capacity,
        exclusive=exclusive,
    )


def make_work_item(
    work_id: str = "TASK_RED",
    *,
    hours: float = 1,
    mandatory: bool = False,
    work_type: str = "delivery",
    dependencies: list[str] | None = None,
    skills: list[SkillRequirement] | None = None,
    languages: list[str] | None = None,
    resources: list[ResourceRequirement] | None = None,
    earliest: date = PLAN_START,
    due: date = PLAN_END,
    revenue: int | float = 0,
    direct_cost: int | float = 0,
    committed: bool = False,
    cash_in_days: int | None = None,
    probability: float = 1.0,
    customer_id: str | None = None,
    strategic_value: float = 1,
) -> WorkItem:
    return WorkItem(
        id=work_id,
        title=work_id,
        type=work_type,
        mandatory=mandatory,
        committed=committed,
        customer_id=customer_id,
        revenue_jpy=revenue,
        direct_cost_jpy=direct_cost,
        cash_in_days=cash_in_days,
        success_probability=probability,
        required_hours=hours,
        earliest_start=earliest,
        due_date=due,
        late_penalty_jpy_per_day=0,
        strategic_value=strategic_value,
        required_skills=[] if skills is None else skills,
        required_languages=[] if languages is None else languages,
        resource_requirements=[] if resources is None else resources,
        dependencies=[] if dependencies is None else dependencies,
        conflicts=[],
    )


def make_option(
    work_item_id: str = "CLIENT_EXPANSION",
    option_id: str = "OPTION_PREMIUM",
    *,
    price: int | float = 1_000,
    cost: int | float = 100,
    delivery_hours: float = 1,
    probability: float = 0.5,
    payment_days: int = 0,
    follow_on: int | float = 0,
    dependencies: list[str] | None = None,
) -> CommercialOption:
    return CommercialOption(
        work_item_id=work_item_id,
        option_id=option_id,
        label=option_id,
        price_jpy=price,
        direct_cost_jpy=cost,
        delivery_hours=delivery_hours,
        payment_days=payment_days,
        estimated_win_probability=probability,
        follow_on_value_jpy=follow_on,
        dependencies=[] if dependencies is None else dependencies,
    )


def make_effect(
    effect_id: str,
    *,
    trigger: str,
    targets: list[str],
    effect_type: str,
    **values,
) -> PortfolioEffect:
    return PortfolioEffect(
        id=effect_id,
        trigger=trigger,
        targets=targets,
        effect={"type": effect_type, **values},
    )


def make_dataset(
    *,
    people: list[Person] | None = None,
    work_items: list[WorkItem] | None = None,
    customers: list[Customer] | None = None,
    resources: list[SharedResource] | None = None,
    options: list[CommercialOption] | None = None,
    effects: list[PortfolioEffect] | None = None,
    start: date = PLAN_START,
    end: date = PLAN_END,
    starting_cash: int = 1_000_000,
    fixed_outflow: int = 0,
    minimum_buffer: int = 0,
    dataset_id: str = "UNSEEN_RELIABILITY_DATASET",
) -> CandidateDataset:
    return CandidateDataset(
        metadata=Metadata(
            dataset_id=dataset_id,
            version="3.0-test",
            planning_start=start,
            planning_end=end,
            currency="JPY",
        ),
        company=Company(
            name="Synthetic Reliability Co",
            starting_cash_jpy=starting_cash,
            fixed_cash_outflow_jpy=fixed_outflow,
            minimum_cash_buffer_jpy=minimum_buffer,
        ),
        people=[make_person()] if people is None else people,
        customers=[] if customers is None else customers,
        shared_resources=[] if resources is None else resources,
        work_items=[] if work_items is None else work_items,
        commercial_options=[] if options is None else options,
        portfolio_effects=[] if effects is None else effects,
        enumerations=Enumerations(
            work_item_types=["delivery", "sales_opportunity", "internal"],
            skills=["general", "robotics", "forensics", "quantum_simulation", "legal_review"],
            languages=["EN", "JA", "VI", "FR"],
        ),
    )


@dataclass(frozen=True)
class PipelineRun:
    feasibility: list[FeasibilityResult]
    portfolio: PortfolioEffectsResult
    commercial: CommercialEvaluationResult
    scoring: ScoringResult
    plan: PlanResult
    cash: CashFlowResult
    final: FinalDecisionResult


def run_pipeline(
    dataset: CandidateDataset,
    *,
    completed: frozenset[str] = frozenset(),
    scoring_reference: ScoringReference | None = None,
) -> PipelineRun:
    feasibility = FeasibilityEngine().check_all(dataset, completed_ids=completed)
    portfolio_engine = PortfolioEffectsEngine()
    context = portfolio_engine.build_context_from_dataset(
        dataset,
        completed_work_item_ids=completed,
    )
    portfolio = portfolio_engine.evaluate(dataset, context)
    commercial = CommercialEvaluationEngine().evaluate(
        dataset,
        portfolio,
        completed_ids=completed,
    )
    scoring = ScoringEngine().evaluate(
        dataset,
        portfolio,
        commercial,
        feasibility_results=feasibility,
        scoring_reference=scoring_reference,
        completed_ids=completed,
    )
    plan = PlannerEngine().plan(
        dataset,
        completed_work_item_ids=completed,
        scoring_reference=scoring_reference,
    )
    cash = CashFlowSimulator().simulate(dataset, plan)
    final = FinalValidationEngine().validate(dataset, plan, cash)
    return PipelineRun(feasibility, portfolio, commercial, scoring, plan, cash, final)
