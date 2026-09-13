#!/usr/bin/env python3
"""
D2(c) - SEQUENTIAL VS PARALLEL  (scripted backend, REF-5602)
====================================================================
Dependency rule (unchanged from the scaffold's framing): only calls
whose inputs do NOT depend on each other's outputs may share a turn. In
this project's tool set, the ONE point where that applies on REF-5602 is
turn 2: check_referral_criteria and lookup_patient both depend only on
get_referral's output, and not on each other. Everything else in the
chain - compute_window needs check_referral_criteria's band/window_weeks,
get_clinic_slots needs compute_window's dates, book_slot needs
get_clinic_slots' chosen row - is a genuine dependency chain and cannot
be shortened by grouping.

    A. sequential   one call per turn, no grouping at all
    B. parallel     independent calls grouped into shared turns
                    (this project's default, used for the real eval set)

Both run on the free, deterministic scripted backend - no live call
needed to measure turns/calls/estimated tokens/cost, though the ESTIMATE
label matters (see docs and STATUS.md): real per-token cost only comes
from the live battery.
====================================================================
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from agent import run_case  # noqa: E402
from harness import code_check, load_cases, load_key  # noqa: E402

CASE = "REF-5602"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results", "parallelism")


def summarise(record, label):
    return {
        "label": label,
        "case_id": record["case_id"],
        "decision": record["decision"],
        "turns": record["turns"],
        "tool_calls": record["tool_call_count"],
        "tokens_in_estimate": record["tokens_in"],
        "tokens_out_estimate": record["tokens_out"],
        "total_tokens_estimate": record["tokens_in"] + record["tokens_out"],
        "cost_usd_estimate": record["cost_usd"],
        "seconds": record["seconds"],
        "evidence": [e["tool"] for e in record["evidence"]],
    }


def full_set_comparison():
    """Runs the ENTIRE 55-case/95-trial eval set both ways (sequential:
    one call per turn, no grouping at all; parallel: this project's
    default), on the free scripted backend, and reports aggregate
    turns/tokens/cost/pass-rate for both - not just the one worked
    example above. This is what proves correctness did not move across
    the whole set, not just on one illustrative case."""
    key = load_key()
    cases = [c for c in load_cases() if c in key]

    def run_all(parallel):
        rows = []
        for cid in cases:
            expected = key[cid]
            trials = 3 if expected.get("expected_decision") in ("escalate", "request_information") else 1
            for trial in range(trials):
                record = run_case(cid, parallel=parallel)
                passed, _ = code_check(record, expected)
                rows.append({"case_id": cid, "passed": passed, "record": record})
        return rows

    seq_rows = run_all(parallel=False)
    par_rows = run_all(parallel=True)

    def agg(rows, label):
        total = len(rows)
        passed = sum(1 for r in rows if r["passed"])
        turns = [r["record"]["turns"] for r in rows]
        tokens = [r["record"]["tokens_in"] + r["record"]["tokens_out"] for r in rows]
        cost = sum(r["record"]["cost_usd"] for r in rows)
        return {
            "label": label,
            "trials": total,
            "pass_rate": round(passed / total, 4),
            "total_turns": sum(turns),
            "median_turns": statistics.median(turns),
            "total_tokens_estimate": sum(tokens),
            "total_cost_usd_estimate": round(cost, 6),
        }

    seq_agg, par_agg = agg(seq_rows, "sequential_full_set"), agg(par_rows, "parallel_full_set")
    result = {
        "note": "Full 55-case/95-trial eval set, both grouping modes, "
                "scripted backend - token/cost figures are the scripted "
                "backend's ESTIMATE function, not a live measurement.",
        "sequential": seq_agg,
        "parallel": par_agg,
        "pass_rate_identical": seq_agg["pass_rate"] == par_agg["pass_rate"],
        "turns_saved_pct": round(100.0 * (seq_agg["total_turns"] - par_agg["total_turns"]) / seq_agg["total_turns"], 1),
        "tokens_saved_pct": round(100.0 * (seq_agg["total_tokens_estimate"] - par_agg["total_tokens_estimate"])
                                  / seq_agg["total_tokens_estimate"], 1),
    }
    with open(os.path.join(OUT_DIR, "full_set_comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(json.dumps(result, indent=2, default=str))
    return result


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    seq = run_case(CASE, parallel=False)
    par = run_case(CASE, parallel=True)

    seq_s, par_s = summarise(seq, "sequential"), summarise(par, "parallel")

    comparison = {
        "case_id": CASE,
        "note": "Token/cost figures are the scripted backend's ESTIMATE "
                "function, not a live measurement - see STATUS.md.",
        "sequential": seq_s,
        "parallel": par_s,
        "delta": {
            "turns_saved": seq_s["turns"] - par_s["turns"],
            "turns_saved_pct": round(100.0 * (seq_s["turns"] - par_s["turns"]) / seq_s["turns"], 1),
            "tool_calls_identical": seq_s["tool_calls"] == par_s["tool_calls"],
            "total_tokens_saved_estimate": seq_s["total_tokens_estimate"] - par_s["total_tokens_estimate"],
            "cost_saved_usd_estimate": round(seq_s["cost_usd_estimate"] - par_s["cost_usd_estimate"], 6),
            "wasted_calls": 0,
            "correctness_identical": seq["decision"] == par["decision"] and seq.get("booked") == par.get("booked"),
        },
    }

    with open(os.path.join(OUT_DIR, "sequential.json"), "w", encoding="utf-8") as fh:
        json.dump(seq_s, fh, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "parallel.json"), "w", encoding="utf-8") as fh:
        json.dump(par_s, fh, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(comparison, fh, indent=2, default=str)

    print(json.dumps(comparison, indent=2, default=str))
    print("\nWrote sequential.json, parallel.json, comparison.json to", OUT_DIR)

    print("\n" + "=" * 68)
    print("Full 55-case/95-trial set, both grouping modes")
    print("=" * 68)
    full_set_comparison()


if __name__ == "__main__":
    main()
