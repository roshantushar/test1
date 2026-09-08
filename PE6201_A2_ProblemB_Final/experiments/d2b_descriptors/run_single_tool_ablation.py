#!/usr/bin/env python3
"""
D2(b) - REQUIRED EXPERIMENT: descriptor v1 vs v2 for ONE TOOL, model held
fixed, everything else in the prompt held fixed at v2.
====================================================================
This is DIFFERENT from experiments/d2b_descriptors/run_live_comparison.py,
which varies the WHOLE prompt (rules, answer format, every descriptor).
Here only `get_clinic_slots`' own descriptor changes:

  v1 (weak)   prompt.V1_DESCRIPTORS["get_clinic_slots"] - one line, no
              statement that `band` must come from check_referral_criteria
              (not guessed), no statement that an empty list means
              escalate rather than "try again", no statement that this
              must only be called after all five gates pass.
  v2 (good)   tools.DESCRIPTORS["get_clinic_slots"] - the full descriptor
              actually shipped, with all of the above spelled out.

WHY get_clinic_slots: it is the tool the assignment's own example names
("require urgency band + legal date range") and the one whose poka-yoke
(band as a required, filtered argument) this project already leans on
hardest - D7's failure #2 shows what happens when that safeguard is
removed from the TOOL; this experiment asks what happens when the
DESCRIPTION of that same tool is merely weak, with the underlying
Python signature unchanged (band is still a required positional
argument either way - only what the model is TOLD about it changes).

CASE SELECTION: only cases that actually reach get_clinic_slots matter for
this ablation - the 14 `book` cases (which call it and must get the band
right) and the 3 `no_slot_in_window` escalate cases (which call it and
must interpret an empty result correctly). The other 28 cases never call
this tool at all, so re-running them would only spend money to reconfirm
they are unaffected - already implied by the dependency structure.
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


def _relevant_cases():
    from harness import load_cases, load_key
    key = load_key()
    cases = [c for c in load_cases() if c in key]
    relevant = []
    for cid in cases:
        exp = key[cid]
        if exp.get("expected_decision") == "book" or exp.get("trigger") == "no_slot_in_window":
            relevant.append(cid)
    return relevant, key


def run_variant(label):
    import prompt
    import tools
    from harness import code_check
    from agent import run_case

    cases, key = _relevant_cases()
    if label == "v1_weak_get_clinic_slots":
        swap_in = prompt.V1_DESCRIPTORS["get_clinic_slots"]
    else:
        swap_in = tools.DESCRIPTORS["get_clinic_slots"]
    system_prompt = prompt.build_system_prompt_single_tool_swap("get_clinic_slots", swap_in)

    rows = []
    for cid in cases:
        expected = key[cid]
        trials = 3 if expected.get("expected_decision") in ("escalate", "request_information") else 1
        for trial in range(1, trials + 1):
            try:
                record = run_case(cid, system_prompt_override=system_prompt)
            except Exception as e:
                record = {"case_id": cid, "decision": "ERROR", "reason": repr(e),
                          "evidence": [], "turns": 0, "tokens_in": 0, "tokens_out": 0,
                          "cost_usd": 0, "stopped_by": "exception"}
            passed, fails = code_check(record, expected)
            gcs_calls = [e for e in record.get("evidence", []) if e["tool"] == "get_clinic_slots"]
            obs_tokens_est = record.get("tokens_in", 0)  # includes the growing transcript+prompt
            rows.append({"case_id": cid, "trial": trial, "passed": passed, "fails": fails,
                        "record": record, "get_clinic_slots_calls": len(gcs_calls)})
            print("  [%s] %-10s trial %d  %-6s  %s" % (
                label, cid, trial, "PASS" if passed else "FAIL", record.get("decision")))
    return rows


def summarise(rows, label):
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    negatives = [r for r in rows if r["record"].get("decision") == "escalate"]
    neg_passed = sum(1 for r in negatives if r["passed"])
    wasted_gcs_calls = sum(max(0, r["get_clinic_slots_calls"] - 1) for r in rows)
    return {
        "label": label,
        "trials": total,
        "pass_rate": passed / total if total else None,
        "negative_trials": len(negatives),
        "negative_pass_rate": (neg_passed / len(negatives)) if negatives else None,
        "mean_tokens_in": sum(r["record"]["tokens_in"] for r in rows) / total if total else None,
        "mean_tokens_out": sum(r["record"]["tokens_out"] for r in rows) / total if total else None,
        "mean_turns": sum(r["record"]["turns"] for r in rows) / total if total else None,
        "total_cost_usd": sum(r["record"]["cost_usd"] for r in rows),
        "wasted_get_clinic_slots_calls": wasted_gcs_calls,
        "failures": [{"case_id": r["case_id"], "trial": r["trial"], "fails": r["fails"]}
                    for r in rows if not r["passed"]],
    }


def main():
    if config.BACKEND != "live":
        sys.exit(
            "\n  This experiment needs config.BACKEND = 'live' and an API key.\n"
            "  Not run: BACKEND is %r in this environment (see STATUS.md).\n"
            % config.BACKEND)

    os.makedirs(OUT_DIR, exist_ok=True)
    v1_rows = run_variant("v1_weak_get_clinic_slots")
    v2_rows = run_variant("v2_full_get_clinic_slots")
    v1_summary = summarise(v1_rows, "v1_weak_get_clinic_slots")
    v2_summary = summarise(v2_rows, "v2_full_get_clinic_slots")

    out = {
        "tool_under_test": "get_clinic_slots",
        "model": config.MODEL,
        "case_subset": "14 book cases (1 trial) + 3 no_slot_in_window escalate cases (3 trials) = 23 trials/version - only cases that call get_clinic_slots",
        "v1_weak": v1_summary,
        "v2_full": v2_summary,
    }
    with open(os.path.join(OUT_DIR, "single_tool_ablation_get_clinic_slots.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)

    print()
    print("=" * 68)
    print("D2(b) single-tool descriptor ablation: get_clinic_slots")
    print("=" * 68)
    print("%-28s %10s %10s" % ("metric", "v1 weak", "v2 full"))
    print("%-28s %10.1f%% %9.1f%%" % ("pass rate", v1_summary["pass_rate"]*100, v2_summary["pass_rate"]*100))
    print("%-28s %10.1f%% %9.1f%%" % ("negative-case pass rate",
          (v1_summary["negative_pass_rate"] or 0)*100, (v2_summary["negative_pass_rate"] or 0)*100))
    print("%-28s %10.0f %10.0f" % ("avg tokens in", v1_summary["mean_tokens_in"], v2_summary["mean_tokens_in"]))
    print("%-28s %10.0f %10.0f" % ("avg tokens out", v1_summary["mean_tokens_out"], v2_summary["mean_tokens_out"]))
    print("%-28s %10.2f %10.2f" % ("avg turns", v1_summary["mean_turns"], v2_summary["mean_turns"]))
    print("%-28s $%9.4f $%9.4f" % ("total cost", v1_summary["total_cost_usd"], v2_summary["total_cost_usd"]))
    print("%-28s %10d %10d" % ("wasted get_clinic_slots calls", v1_summary["wasted_get_clinic_slots_calls"], v2_summary["wasted_get_clinic_slots_calls"]))


if __name__ == "__main__":
    main()
