#!/usr/bin/env python3
"""
D2(b) - DESCRIPTOR v1 VS v2, ON A LIVE MODEL
====================================================================
Needs `export OPENROUTER_API_KEY=...` and `config.BACKEND = "live"`.
Runs the FULL 35-case, 55-trial evaluation set (D4's trial policy: 1
trial for ordinary cases, 3 for negative ones) under each descriptor
version, so this is directly comparable to results/live/*.json's
single-model D5(b) result - same cases, same trial policy, same model,
only the descriptor set differs.

WHAT IT HOLDS FIXED: model (config.MODEL), the case set (all 35), the
tool set, guardrails (config.MAX_TURNS / MAX_TOKENS_PER_RUN / the
duplicate-check poka-yoke in agent.py, which is enforced by the
orchestration layer regardless of prompt version), autonomy
(config.AUTONOMY), temperature (0, hard-coded in backends._live_call).

WHAT IT VARIES: only prompt.DESCRIPTOR_SETS["v1"] vs ["v2"] - see
src/prompt.py for both sets.

WHAT IT MEASURES (real API usage, not estimates - see
backends.LiveBackend, which reads payload["usage"] from the API
response): trials, pass rate, negative-case pass rate, input tokens,
output tokens, turns, cost, and every failure.
====================================================================
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import config  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "descriptors")


def run_version(version):
    from harness import code_check, load_cases, load_key
    from agent import run_case

    key = load_key()
    cases = [c for c in load_cases() if c in key]
    rows = []
    for cid in cases:
        expected = key[cid]
        trials = 3 if expected.get("expected_decision") in (
            "escalate", "request_information") else 1
        for trial in range(1, trials + 1):
            try:
                record = run_case(cid, descriptor_version=version)
            except Exception as e:
                record = {"case_id": cid, "decision": "ERROR", "reason": repr(e),
                          "evidence": [], "turns": 0, "tokens_in": 0, "tokens_out": 0,
                          "cost_usd": 0, "stopped_by": "exception"}
            passed, fails = code_check(record, expected)
            rows.append({"case_id": cid, "trial": trial, "passed": passed,
                        "fails": fails, "record": record, "family": expected.get("family")})
            print("  [%s] %-10s trial %d  %-6s  %s" % (
                version, cid, trial, "PASS" if passed else "FAIL", record.get("decision")))
    return rows


def summarise(rows, version):
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    negatives = [r for r in rows if r["record"].get("decision") in
                 ("escalate", "request_information")]
    neg_passed = sum(1 for r in negatives if r["passed"])
    return {
        "descriptor_version": version,
        "trials": total,
        "pass_rate": passed / total if total else None,
        "negative_trials": len(negatives),
        "negative_pass_rate": (neg_passed / len(negatives)) if negatives else None,
        "mean_tokens_in": sum(r["record"]["tokens_in"] for r in rows) / total if total else None,
        "mean_tokens_out": sum(r["record"]["tokens_out"] for r in rows) / total if total else None,
        "mean_turns": sum(r["record"]["turns"] for r in rows) / total if total else None,
        "total_cost_usd": sum(r["record"]["cost_usd"] for r in rows),
        "failures": [{"case_id": r["case_id"], "trial": r["trial"], "fails": r["fails"]}
                    for r in rows if not r["passed"]],
    }


def main():
    if config.BACKEND != "live":
        sys.exit(
            "\n  This experiment needs config.BACKEND = 'live' and an API key.\n"
            "  Not run: BACKEND is %r in this environment (see STATUS.md).\n"
            "  To run for real:\n"
            "    export OPENROUTER_API_KEY='sk-or-...'\n"
            "    edit src/config.py: BACKEND = 'live'\n"
            "    python3 experiments/d2b_descriptors/run_live_comparison.py\n"
            % config.BACKEND)

    os.makedirs(OUT_DIR, exist_ok=True)
    v1_rows = run_version("v1")
    v2_rows = run_version("v2")
    v1_summary = summarise(v1_rows, "v1")
    v2_summary = summarise(v2_rows, "v2")

    with open(os.path.join(OUT_DIR, "v1_live.json"), "w", encoding="utf-8") as fh:
        json.dump({"summary": v1_summary, "trials": v1_rows}, fh, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "v2_live.json"), "w", encoding="utf-8") as fh:
        json.dump({"summary": v2_summary, "trials": v2_rows}, fh, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "comparison.json"), "w", encoding="utf-8") as fh:
        json.dump({"model": config.MODEL, "v1": v1_summary, "v2": v2_summary}, fh, indent=2, default=str)

    print(json.dumps({"v1": v1_summary, "v2": v2_summary}, indent=2, default=str))


if __name__ == "__main__":
    main()
