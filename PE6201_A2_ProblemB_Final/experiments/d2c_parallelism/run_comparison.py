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
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from agent import run_case  # noqa: E402

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


if __name__ == "__main__":
    main()
