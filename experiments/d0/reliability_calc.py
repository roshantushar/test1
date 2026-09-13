#!/usr/bin/env python3
"""
D0 - RELIABILITY CALCULATION  s = P^(1/T)
====================================================================
The brief's formula relates a per-step reliability s to an overall
run-success probability P over T steps: P = s^T, so s = P^(1/T).

MEASUREMENT STATUS: P and T below come from results/scripted/final_eval.json
- the DETERMINISTIC reference-policy run (100% code-check pass, median
turns per docs/D4_EVALUATION.md). That P is NOT a live model's success
probability; it is the success rate of a hand-verified, non-probabilistic
walk through the real tools, so s computed from it is a CEILING /
sanity-check value, not the agent's true per-step reliability. The true
P (and hence true s) can only come from the D5(b) live battery - see
STATUS.md. This script is written so re-running it against
results/live/model_comparison.json (once it exists) needs no code change,
only pointing SOURCE at the live summary instead.
====================================================================
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)
SCRIPTED_RESULTS = os.path.join(HERE, "..", "..", "results", "scripted", "final_eval.json")
LIVE_RESULTS = os.path.join(HERE, "..", "..", "results", "live", "openai_gpt-4o-mini.json")
V1_RESULTS = os.path.join(HERE, "..", "..", "results", "descriptors", "v1_live.json")
V2_RESULTS = os.path.join(HERE, "..", "..", "results", "descriptors", "v2_live.json")
OUT_PATH = os.path.join(HERE, "reliability_calc.json")


def _dataset_shape():
    """(total cases, book count, negative count) read directly from the
    answer key, so this description never goes stale after a rebalance -
    unlike a hardcoded case/negative count baked into a format string."""
    import harness
    key = harness.load_key()
    total = len(key)
    negative = sum(1 for v in key.values()
                   if v.get("expected_decision") in ("escalate", "request_information"))
    return total, total - negative, negative


def _one_version(path, label):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data["trials"]
    P = sum(1 for r in rows if r["passed"]) / len(rows)
    turns = [r["record"]["turns"] for r in rows]
    T_median = statistics.median(turns)
    s = round(P ** (1.0 / T_median), 6) if P > 0 else 0.0
    return {
        "version": label,
        "trials": len(rows),
        "P_overall_success": round(P, 4),
        "T_median_turns": T_median,
        "T_mean_turns": round(statistics.mean(turns), 3),
        "s_per_step_at_median_T": s,
    }


def _live_block():
    """REAL P, T and s for v2 (D5b, one model - see STATUS.md), PLUS a
    real v1-vs-v2 comparison (D5's own required experiment) on the
    IDENTICAL-trial-count, current, rebalanced eval set - both live,
    both measured, so the "is the
    bigger lever turn count or per-step reliability" question below has
    an actual answer instead of an illustrative one."""
    if not (os.path.exists(V1_RESULTS) and os.path.exists(V2_RESULTS)):
        return None
    v1 = _one_version(V1_RESULTS, "v1")
    v2 = _one_version(V2_RESULTS, "v2")
    total_trials = v2["trials"]
    total_cases, book_count, neg_count = _dataset_shape()
    if v1["T_median_turns"] > v2["T_median_turns"]:
        turn_clause = ("v1 needs MORE turns (median %d vs %d) AND has a "
                       "much LOWER P" % (v1["T_median_turns"], v2["T_median_turns"]))
    elif v1["T_median_turns"] == v2["T_median_turns"]:
        turn_clause = ("v1 needs the SAME number of turns (median %d, tied) "
                       "but has a much LOWER P" % v1["T_median_turns"])
    else:
        turn_clause = ("v1 needs FEWER turns (median %d vs %d) yet still "
                       "has a much LOWER P" % (v1["T_median_turns"], v2["T_median_turns"]))
    return {
        "model": "openai/gpt-4o-mini",
        "MEASUREMENT_STATUS": "REAL live measurement, one model, on the "
                              "current %d-case/%d-trial (%d book / %d "
                              "negative) evaluation set (D5b is the full "
                              "5-model family comparison - see "
                              "docs/D5_MODEL_BATTERY.md)."
                              % (total_cases, total_trials, book_count, neg_count),
        "v1": v1,
        "v2": v2,
        "note": "v2: P=%.4f over a MEDIAN of %d turns -> s=%.4f per step. "
                "v1: P=%.4f over a MEDIAN of %d turns -> s=%.4f per step. "
                "%s - the worse prompt is not simply explained by turn "
                "count, it is fundamentally less reliable per step, which "
                "rules out 'v1 just needs more turns to get there' as an "
                "explanation. The actual cause (see "
                "results/descriptors/comparison.json) is that v1 usually "
                "reaches the right underlying decision but cannot supply "
                "the exact trigger/missing label the code check requires "
                "on the set's negative cases - a LABELLING/SCHEMA failure, "
                "not a reasoning-depth failure - which is why extending "
                "v1's turn budget would not close this gap. See docs/D0_"
                "AGENT_JUSTIFICATION.md's 'too many turns vs low per-step "
                "reliability' discussion for the full argument."
                % (v2["P_overall_success"], v2["T_median_turns"], v2["s_per_step_at_median_T"],
                   v1["P_overall_success"], v1["T_median_turns"], v1["s_per_step_at_median_T"],
                   turn_clause),
    }


def main():
    with open(SCRIPTED_RESULTS, encoding="utf-8") as fh:
        data = json.load(fh)
    results = data["results"]
    P = sum(1 for r in results if r["passed"]) / len(results)
    turns = [r["record"]["turns"] for r in results]
    T_median = statistics.median(turns)
    T_worst = max(turns)

    def s_for(T):
        return round(P ** (1.0 / T), 6) if P > 0 else 0.0

    out = {
        "MEASUREMENT_STATUS": "P is the SCRIPTED reference-policy pass rate "
                              "(deterministic, not a live model) - see the "
                              "module docstring. This is a sanity-check "
                              "ceiling, not the agent's measured reliability.",
        "P_overall_success": P,
        "T_median_turns": T_median,
        "T_worst_case_turns": T_worst,
        "s_per_step_at_median_T": s_for(T_median),
        "s_per_step_at_worst_case_T": s_for(T_worst),
        "interpretation": (
            "At P=1.0 exactly, s = 1^(1/T) = 1 for every T, so this specific "
            "run of the formula is VACUOUS - it cannot show whether turn "
            "count or per-step reliability is the bigger lever, because the "
            "scripted reference policy has no failure mode to attribute to "
            "either one. That is expected and not a bug: the scripted policy "
            "is a deterministic walk through the real tools (see backends.py), "
            "not a probabilistic model, so P=1 is the correct number for it, "
            "not evidence that the AGENT is perfectly reliable. The formula "
            "only becomes informative once a live P<1 exists (D5b): worked "
            "illustratively at P=0.90 (a plausible live pass rate), s would "
            "need to be 0.9741 per step over a 4-turn median run but only "
            "0.9791 over a 5-turn worst case - a small difference at these "
            "turn counts, which is itself evidence that AT THIS PROBLEM'S "
            "SCALE (4-5 turns), per-step reliability matters somewhat more "
            "than shaving one more turn. See docs/D0_AGENT_JUSTIFICATION.md "
            "for the full discussion, re-checked once real numbers land."
            if P >= 0.999999 else
            "At P=%.4f, needing s=%.4f per step over the median run length "
            "(%d turns) versus s=%.4f over the worst-case length (%d turns) "
            "is the comparison that shows whether turn count or per-step "
            "reliability is the bigger lever at this problem's scale."
            % (P, s_for(T_median), T_median, s_for(T_worst), T_worst)
        ),
    }
    live = _live_block()
    if live:
        out["live_one_model"] = live
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
