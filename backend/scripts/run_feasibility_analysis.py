"""Development script: run Feasibility Engine against the canonical dataset
and print a structured summary.

Usage:
    cd backend
    python scripts/run_feasibility_analysis.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

# Allow running from backend/ or root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.decision_engine.feasibility import FeasibilityEngine, FeasibilityStatus
from app.decision_engine.feasibility.reason_codes import ReasonCode
from app.services.dataset_loader import load_dataset

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "candidate_dataset.json"
SCHEMA = ROOT / "data" / "candidate_dataset.schema.json"

SEPARATOR = "-" * 70

def main() -> None:
    dataset = load_dataset(DATASET, SCHEMA)
    engine = FeasibilityEngine()
    results = engine.check_all(dataset)

    work_map = {w.id: w for w in dataset.work_items}

    feasible = [r for r in results if r.status == FeasibilityStatus.FEASIBLE]
    blocked = [r for r in results if r.status == FeasibilityStatus.BLOCKED]
    infeasible = [r for r in results if r.status == FeasibilityStatus.INFEASIBLE]

    print(SEPARATOR)
    print("NEXAWORKS — PHASE 2A BASE FEASIBILITY ANALYSIS")
    print("Dataset:", dataset.metadata.dataset_id, "| Planning:",
          dataset.metadata.planning_start, "->", dataset.metadata.planning_end)
    print(SEPARATOR)
    print()
    print("DISCLAIMER: This is BASE FEASIBILITY only.")
    print("A work item being FEASIBLE does NOT mean all feasible items")
    print("can be executed simultaneously. That is the Planner's role (Phase 2E).")
    print()
    print(SEPARATOR)
    print(f"Total work items : {len(results)}")
    print(f"  FEASIBLE       : {len(feasible)}")
    print(f"  BLOCKED        : {len(blocked)}")
    print(f"  INFEASIBLE     : {len(infeasible)}")
    print(SEPARATOR)

    # --- FEASIBLE ---
    if feasible:
        print("\n[FEASIBLE] work items:")
        for r in feasible:
            w = work_map[r.work_item_id]
            mandatory_tag = " [MANDATORY]" if w.mandatory else ""
            warn_count = len(r.warnings)
            warn_tag = f"  ({warn_count} warning(s))" if warn_count else ""
            print(f"  {r.work_item_id:6s} | {w.type:20s} | {w.required_hours:>5.0f}h{mandatory_tag}{warn_tag}")

    # --- BLOCKED ---
    if blocked:
        print("\n[BLOCKED] work items:")
        for r in blocked:
            w = work_map[r.work_item_id]
            mandatory_tag = " [MANDATORY]" if w.mandatory else ""
            dep_blockers = [b for b in r.blockers if b.code == ReasonCode.DEPENDENCY_NOT_SATISFIED]
            missing_deps = [b.details["dependency_id"] for b in dep_blockers]
            print(f"  {r.work_item_id:6s} | {w.type:20s} | {w.required_hours:>5.0f}h{mandatory_tag}")
            if missing_deps:
                print(f"         waiting on: {', '.join(missing_deps)}")

    # --- INFEASIBLE ---
    if infeasible:
        print("\n[INFEASIBLE] work items:")
        for r in infeasible:
            w = work_map[r.work_item_id]
            mandatory_tag = " [MANDATORY]" if w.mandatory else ""
            print(f"  {r.work_item_id:6s} | {w.type:20s} | {w.required_hours:>5.0f}h{mandatory_tag}")
            for f in r.hard_failures:
                detail_str = ", ".join(f"{k}={v}" for k, v in f.details.items()
                                       if k not in ("policy", "note"))
                print(f"         [!] {f.code.value}: {detail_str}")

    # --- Mandatory summary ---
    print()
    print(SEPARATOR)
    mandatory_ids = {w.id for w in dataset.work_items if w.mandatory}
    mandatory_results = [r for r in results if r.work_item_id in mandatory_ids]
    mand_feasible = sum(1 for r in mandatory_results if r.status == FeasibilityStatus.FEASIBLE)
    mand_blocked = sum(1 for r in mandatory_results if r.status == FeasibilityStatus.BLOCKED)
    mand_infeasible = sum(1 for r in mandatory_results if r.status == FeasibilityStatus.INFEASIBLE)
    print("MANDATORY ITEM SUMMARY:")
    print(f"  Total mandatory  : {len(mandatory_ids)}")
    print(f"  FEASIBLE         : {mand_feasible}")
    print(f"  BLOCKED          : {mand_blocked}")
    print(f"  INFEASIBLE       : {mand_infeasible}")
    print(SEPARATOR)

    # --- Capacity note ---
    total_cap = sum(p.capacity_hours for p in dataset.people)
    total_work = sum(w.required_hours for w in dataset.work_items)
    feasible_work = sum(work_map[r.work_item_id].required_hours for r in feasible)
    blocked_work = sum(work_map[r.work_item_id].required_hours for r in blocked)
    print()
    print("CAPACITY CONTEXT (informational):")
    print(f"  Total team capacity   : {total_cap:.0f}h")
    print(f"  Total workload (all)  : {total_work:.0f}h  ({total_work/total_cap*100:.0f}% of capacity)")
    print(f"  Feasible items total  : {feasible_work:.0f}h")
    print(f"  Blocked items total   : {blocked_work:.0f}h")
    print(f"  Note: Planner must select a subset — not all feasible items fit simultaneously.")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
