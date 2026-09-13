#!/usr/bin/env python3
"""
D7 FAILURE 1 - LOOP / CONTROL FAILURE  (working agent MINUS de-duplication)
====================================================================
Wraps src/demo_loop_failure.py and saves before/broken/restored evidence
to results/d7/failure_1_loop.json. Scripted backend only.
====================================================================
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import config                                     # noqa: E402
from agent import run_case                         # noqa: E402
from guardrails import Guardrails                   # noqa: E402
import backends                                     # noqa: E402
import copy                                         # noqa: E402
import harness                                      # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "d7")
SCRIPTED_RESULTS = os.path.join(HERE, "..", "..", "results", "scripted", "final_eval.json")
CASE = "REF-5602"


def _measure(record, label):
    return {"label": label, "decision": record["decision"],
            "booked": record.get("booked"), "turns": record["turns"],
            "tool_calls": record["tool_call_count"],
            "tokens_total": record["tokens_in"] + record["tokens_out"],
            "cost_usd": record["cost_usd"], "stopped_by": record["stopped_by"],
            "guardrails_fired": record["guardrails_fired"],
            "pass": record["decision"] == "book"
                    and (record.get("booked") or {}).get("clinic") == "OPH-C2"}


def _looping_moves(case_id):
    real = backends.ScriptedPolicyBackend(case_id)._derive_moves()
    repeat = copy.deepcopy(real[1])
    repeat["thought"] = "Let me check the criteria again to be sure."
    return real[:2] + [repeat, repeat] + real[2:]


def _turn_distribution():
    """The instrumentation that found this failure, reported as a
    DISTRIBUTION - "one number is not a distribution." Read from the
    existing full scripted eval run (results/scripted/final_eval.json),
    not re-run here - the same 95-trial run reported everywhere else in
    this project, so this is exactly the evidence the step cap (8) and
    budget ceiling (60,000) were set from."""
    with open(SCRIPTED_RESULTS, encoding="utf-8") as fh:
        data = json.load(fh)
    turns = [r["record"]["turns"] for r in data["results"]]
    step_cap_hits = sum(1 for r in data["results"]
                        if r["record"].get("stopped_by") == "step_cap")
    return {
        "trials": len(turns),
        "median_turns": statistics.median(turns),
        "mean_turns": round(statistics.mean(turns), 3),
        "worst_case_turns": max(turns),
        "min_turns": min(turns),
        "trials_hitting_step_cap": step_cap_hits,
        "step_cap": config.MAX_TURNS,
    }


def _full_set_pass_rate_with_dedup_disabled():
    """Runs the FULL 55-case/95-trial scripted set with action
    de-duplication disabled (guard #3 removed globally, exactly the
    same deletion as the one-case failure below) but WITHOUT forcing
    any looping transcript - showing the deletion alone, on ordinary
    runs, does not change the pass rate. The scripted reference policy
    never naturally repeats an identical call on its own, so this
    demonstrates the guard's ABSENCE is invisible on normal runs - the
    same "no exception, nothing looks wrong" property that makes this
    failure mode dangerous, and exactly why a forced repeat (below) is
    needed to actually exercise it."""
    key = harness.load_key()
    cases = [c for c in harness.load_cases() if c in key]
    real_check = Guardrails.check_duplicate
    Guardrails.check_duplicate = lambda self, tool, args: None
    try:
        rows = []
        for cid in cases:
            expected = key[cid]
            trials = 3 if expected.get("expected_decision") in ("escalate", "request_information") else 1
            for _ in range(trials):
                record = run_case(cid)
                passed, _ = harness.code_check(record, expected)
                rows.append(passed)
    finally:
        Guardrails.check_duplicate = real_check
    return {"trials": len(rows), "passed": sum(rows),
           "pass_rate": round(sum(rows) / len(rows), 4)}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    before = run_case(CASE)

    real_check = Guardrails.check_duplicate
    Guardrails.check_duplicate = lambda self, tool, args: None
    try:
        broken = run_case(CASE, force_moves=_looping_moves(CASE))
    finally:
        Guardrails.check_duplicate = real_check

    restored = run_case(CASE)   # guard back in place, unmodified case

    out = {
        "failure": "loop_control - action de-duplication removed",
        "layer": "code (guardrails.py)",
        "method": "working agent minus X, X restored",
        "before": _measure(before, "before (guard in place)"),
        "broken": _measure(broken, "broken (guard deleted, model repeats a call)"),
        "restored": _measure(restored, "restored (guard back in place)"),
    }
    out["unsafe_booking"] = False   # this failure wastes cost, it does not book wrongly
    out["cost_multiplier_broken_over_before"] = round(
        out["broken"]["tokens_total"] / max(1, out["before"]["tokens_total"]), 2)
    out["same_answer_before_and_broken"] = (
        out["before"]["decision"] == out["broken"]["decision"]
        and out["before"]["booked"] == out["broken"]["booked"])
    _compare_fields = ["decision", "booked", "turns", "tool_calls",
                       "tokens_total", "cost_usd", "stopped_by"]
    out["restored_matches_before"] = all(
        out["restored"][f] == out["before"][f] for f in _compare_fields)

    # Item 2 (turn distribution) and item 4 (pass rate did not fall,
    # across the WHOLE eval set, not just this one case) of the
    # assignment's required "four things to report" for Failure 1.
    out["turn_distribution"] = _turn_distribution()
    out["full_set_pass_rate_with_guard_disabled"] = _full_set_pass_rate_with_dedup_disabled()

    with open(os.path.join(OUT_DIR, "failure_1_loop.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
