#!/usr/bin/env python3
"""
D5(b) - LIVE MODEL BATTERY
====================================================================
NOT YET RUN in this environment - see STATUS.md. Only to be run after:
  * the evaluation set is frozen (data/expected_outcomes_B.json - done)
  * the v2 prompt is frozen (src/prompt.py DESCRIPTOR_SETS["v2"] - done)
  * tools are frozen (src/tools.py - done)
  * guards are frozen (src/guardrails.py, config.py limits - done)
  * the scripted run works (results/scripted/final_eval.json - done,
    100% pass, see STATUS.md)

Holds fixed: the v2 prompt, the full 35-case data set, the tool set,
the guardrails, autonomy, and all other config. Only MODEL changes
across the models listed in MODELS below - edit that list to the
families you have access to via OpenRouter.

Captures ACTUAL provider usage (backends.LiveBackend reads
payload["usage"] from each API response) - not an estimate.

    export OPENROUTER_API_KEY='sk-or-...'
    edit src/config.py: BACKEND = 'live'
    python3 experiments/d5_models/run_live_battery.py
====================================================================
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import config  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "live")

# Edit to the model families you actually have OpenRouter access to.
# openai/gpt-4o-mini already run separately - see results/live/openai_gpt-4o-mini.json.
# google/gemini-flash-1.5 does not exist on this OpenRouter account's catalog;
# substituted with google/gemini-2.5-flash-lite (same cheap/fast Gemini tier).
# anthropic/claude-3-haiku was replaced with qwen/qwen-2.5-72b-instruct
# per explicit request - claude-3-haiku's 0% result is kept and reported
# separately (see results/live/anthropic_claude-3-haiku.json) as a real
# protocol-compliance finding, not discarded.
MODELS = [
    "qwen/qwen-2.5-72b-instruct",
    "google/gemini-2.5-flash-lite",
]


def run_one_model(model_id):
    config.MODEL = model_id
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
            record = run_case(cid, descriptor_version="v2")
            passed, fails = code_check(record, expected)
            rows.append({"case_id": cid, "trial": trial, "passed": passed,
                        "fails": fails, "record": record})
    return rows


def summarise(rows, model_id):
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    return {
        "model": model_id,
        "trials": total,
        "passed": passed,
        "pass_rate": passed / total if total else None,
        "mean_turns": sum(r["record"]["turns"] for r in rows) / total if total else None,
        "total_tokens_in": sum(r["record"]["tokens_in"] for r in rows),
        "total_tokens_out": sum(r["record"]["tokens_out"] for r in rows),
        "total_cost_usd": sum(r["record"]["cost_usd"] for r in rows),
    }


def main():
    if config.BACKEND != "live":
        sys.exit(
            "\n  This experiment needs config.BACKEND = 'live' and an API key.\n"
            "  Not run: BACKEND is %r in this environment (see STATUS.md).\n"
            % config.BACKEND)

    os.makedirs(OUT_DIR, exist_ok=True)
    comparison = []
    for model_id in MODELS:
        rows = run_one_model(model_id)
        summary = summarise(rows, model_id)
        comparison.append(summary)
        safe_name = model_id.replace("/", "_")
        with open(os.path.join(OUT_DIR, "%s.json" % safe_name), "w", encoding="utf-8") as fh:
            json.dump({"summary": summary, "trials": rows}, fh, indent=2, default=str)

    with open(os.path.join(OUT_DIR, "model_comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(comparison, fh, indent=2, default=str)
    print(json.dumps(comparison, indent=2, default=str))


if __name__ == "__main__":
    main()
