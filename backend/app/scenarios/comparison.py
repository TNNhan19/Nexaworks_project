from __future__ import annotations

from .errors import InvalidRunStateError
from .models import RunComparison, ScenarioRun


def _transition(a: dict, b: dict, key: str) -> dict[str, str]:
    return {"from": a[key], "to": b[key]}


def _set_delta(a: list[str], b: list[str]) -> dict[str, list[str]]:
    a_set, b_set = set(a), set(b)
    return {"added": sorted(b_set - a_set), "removed": sorted(a_set - b_set)}


def _numeric(a: int | float | None, b: int | float | None) -> dict:
    return {"run_a": a, "run_b": b, "delta": None if a is None or b is None else b - a}


def _cash_scenario(run: ScenarioRun, name: str) -> dict:
    return run.cash_flow.get("scenarios", {}).get(name, {})


def compare_runs(run_a: ScenarioRun, run_b: ScenarioRun) -> RunComparison:
    if run_a.status != "COMPLETED" or run_b.status != "COMPLETED":
        raise InvalidRunStateError("Only completed runs can be compared")
    fa, fb = run_a.final_decision, run_b.final_decision
    pa, pb = run_a.plan, run_b.plan
    ea, eb = fa["executive_summary"], fb["executive_summary"]
    expected_a, expected_b = _cash_scenario(run_a, "EXPECTED"), _cash_scenario(run_b, "EXPECTED")
    downside_a, downside_b = _cash_scenario(run_a, "DOWNSIDE"), _cash_scenario(run_b, "DOWNSIDE")
    success_a, success_b = _cash_scenario(run_a, "SUCCESS"), _cash_scenario(run_b, "SUCCESS")
    breach_a = bool(
        expected_a.get("buffer_breach_dates")
        or downside_a.get("buffer_breach_dates")
        or success_a.get("buffer_breach_dates")
    )
    breach_b = bool(
        expected_b.get("buffer_breach_dates")
        or downside_b.get("buffer_breach_dates")
        or success_b.get("buffer_breach_dates")
    )
    return RunComparison(
        run_a_id=run_a.run_id,
        run_b_id=run_b.run_id,
        status_transition={
            key: _transition(fa, fb, key)
            for key in ("overall_status", "operational_status", "financial_status")
        },
        selected=_set_delta(pa.get("selected_actions", []), pb.get("selected_actions", [])),
        delayed=_set_delta(pa.get("delayed_actions", []), pb.get("delayed_actions", [])),
        no_bid=_set_delta(pa.get("no_bid_opportunities", []), pb.get("no_bid_opportunities", [])),
        capacity={
            "used_hours": _numeric(ea["total_used_hours"], eb["total_used_hours"]),
            "remaining_hours": _numeric(ea["total_remaining_hours"], eb["total_remaining_hours"]),
        },
        cash={
            "expected_ending_cash_jpy": _numeric(expected_a.get("ending_cash_jpy"), expected_b.get("ending_cash_jpy")),
            "downside_ending_cash_jpy": _numeric(downside_a.get("ending_cash_jpy"), downside_b.get("ending_cash_jpy")),
            "minimum_cash_jpy": _numeric(ea.get("minimum_cash_jpy"), eb.get("minimum_cash_jpy")),
        },
        buffer_breach={
            "run_a": breach_a,
            "run_b": breach_b,
            "change": "UNCHANGED" if breach_a == breach_b else ("STARTED" if breach_b else "RESOLVED"),
        },
        major_risks=_set_delta(ea.get("major_risks", []), eb.get("major_risks", [])),
        major_strengths=_set_delta(ea.get("major_strengths", []), eb.get("major_strengths", [])),
    )
