#!/usr/bin/env python3
"""
D2(b) - REQUIRED EXPERIMENT: descriptor v1 vs v2 for ONE TOOL, model held
fixed, everything else in the prompt held fixed at v2.
====================================================================
This is DIFFERENT from experiments/d2b_descriptors/run_live_comparison.py,
which varies the WHOLE prompt (rules, answer format, every descriptor).
Here only `get_clinic_slots` changes - BOTH its descriptor text AND its
return shape together, per the assignment's own framing ("ship a v1 and
a v2 of its descriptor and its return shape"):

  v1 (weak)   prompt.V1_DESCRIPTORS["get_clinic_slots"] - one line, no
              statement that `band` must come from check_referral_criteria
              (not guessed), no statement that an empty list means
              escalate rather than "try again", no statement that this
              must only be called after all five gates pass. PAIRED with
              the VERBOSE return shape: {clinic, specialty, band, date,
              time, capacity_remaining} per row - specialty/band are
              already known to the model (its own call arguments) and
              capacity_remaining is never used once the tool has already
              filtered to capacity>0 rows.
  v2 (good)   tools.DESCRIPTORS["get_clinic_slots"] - the full descriptor
              actually shipped. PAIRED with the COMPACT return shape:
              {clinic, date, time} only - the same rows, same order,
              only the redundant/unused fields dropped.

WHY get_clinic_slots: it is the tool the assignment's own example names
("require urgency band + legal date range") and the one whose poka-yoke
(band as a required, filtered argument) this project already leans on
hardest - D7's failure #2 shows what happens when that safeguard is
removed from the TOOL; this experiment asks what happens when the
DESCRIPTION and RETURN SHAPE of that same tool are both weak, with the
underlying Python signature and band-filtering logic unchanged (band is
still a required, cross-checked positional argument either way).

CASE SELECTION: only cases that actually reach get_clinic_slots matter for
this ablation - the `book` cases (which call it and must get the band
right) and the `no_slot_in_window` escalate cases (which call it and
must interpret an empty result correctly). The rest never call this tool
at all, so re-running them would only spend money to reconfirm they are
unaffected - already implied by the dependency structure.

METRICS REPORTED (per the assignment): evaluation pass rate, tokens
RETURNED PER CALL (the size of get_clinic_slots' own observation, not
the whole prompt - a distinct number from the overall token counts
D5(b) reports), and guardrail-relevant checks passed (band-correctness:
the booked band must equal check_referral_criteria's ASSESSED band, not
a value copied from a slot row - this is exactly the failure D7's
second reproduced failure walks through when the tool's own safeguard
is removed; and call-ordering: get_clinic_slots must never be called
before check_referral_criteria/lookup_patient have both returned).
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

VERBOSE_FIELDS = ("clinic", "specialty", "band", "date", "time", "capacity_remaining")
COMPACT_FIELDS = ("clinic", "date", "time")


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


def _estimate_tokens(obj):
    """~4 chars/token, the standard rough heuristic - used here only to
    size ONE tool's own return payload, not a whole prompt."""
    return len(json.dumps(obj, default=str)) / 4.0


def _guardrail_checks(record, expected):
    """Two guardrail-relevant checks specific to get_clinic_slots' own
    poka-yoke (band as a required, filtered argument - see D7 failure
    #2), computed from the evidence trace already on the record:

    band_correct: for a `book` decision, the band actually passed to
    book_slot must equal check_referral_criteria's ASSESSED band - not
    a value that could have been copied from a slot row instead (the
    exact failure mode D7's second reproduced failure walks through).

    correct_ordering: get_clinic_slots must never appear in the
    evidence trace before BOTH check_referral_criteria and
    lookup_patient have already appeared - calling it earlier means a
    slot search happened before the gates that should have prevented
    it were even checked.
    """
    evidence = record.get("evidence", [])
    tools_seen = [e["tool"] for e in evidence]

    band_correct = True
    if expected.get("expected_decision") == "book":
        crit_obs = next((e["observation"] for e in evidence
                         if e["tool"] == "check_referral_criteria"), None)
        book_obs = next((e["args"] for e in evidence
                         if e["tool"] == "book_slot"), None)
        if crit_obs and book_obs:
            band_correct = crit_obs.get("band") == book_obs.get("band")

    correct_ordering = True
    if "get_clinic_slots" in tools_seen:
        gcs_index = tools_seen.index("get_clinic_slots")
        prior = set(tools_seen[:gcs_index])
        correct_ordering = {"check_referral_criteria", "lookup_patient"} <= prior

    return {"band_correct": band_correct, "correct_ordering": correct_ordering}


def run_variant(label, return_shape):
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

    real_get_clinic_slots = tools.REGISTRY["get_clinic_slots"]
    fields = VERBOSE_FIELDS if return_shape == "verbose" else COMPACT_FIELDS

    def shaped_get_clinic_slots(*a, **kw):
        rows = real_get_clinic_slots(*a, **kw)
        return [{k: r[k] for k in fields} for r in rows]

    tools.REGISTRY["get_clinic_slots"] = shaped_get_clinic_slots
    try:
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
                obs_token_sizes = [_estimate_tokens(e["observation"]) for e in gcs_calls]
                guardrails = _guardrail_checks(record, expected)
                rows.append({"case_id": cid, "trial": trial, "passed": passed, "fails": fails,
                            "record": record, "get_clinic_slots_calls": len(gcs_calls),
                            "get_clinic_slots_observation_tokens": obs_token_sizes,
                            "guardrail_checks": guardrails})
                print("  [%s] %-10s trial %d  %-6s  %s  band_ok=%s  order_ok=%s" % (
                    label, cid, trial, "PASS" if passed else "FAIL", record.get("decision"),
                    guardrails["band_correct"], guardrails["correct_ordering"]))
        return rows
    finally:
        tools.REGISTRY["get_clinic_slots"] = real_get_clinic_slots


def summarise(rows, label):
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    negatives = [r for r in rows if r["record"].get("decision") == "escalate"]
    neg_passed = sum(1 for r in negatives if r["passed"])
    wasted_gcs_calls = sum(max(0, r["get_clinic_slots_calls"] - 1) for r in rows)

    all_obs_tokens = [t for r in rows for t in r["get_clinic_slots_observation_tokens"]]
    band_ok = sum(1 for r in rows if r["guardrail_checks"]["band_correct"])
    order_ok = sum(1 for r in rows if r["guardrail_checks"]["correct_ordering"])

    return {
        "label": label,
        "trials": total,
        "pass_rate": passed / total if total else None,
        "negative_trials": len(negatives),
        "negative_pass_rate": (neg_passed / len(negatives)) if negatives else None,
        "mean_tokens_in": sum(r["record"]["tokens_in"] for r in rows) / total if total else None,
        "mean_tokens_out": sum(r["record"]["tokens_out"] for r in rows) / total if total else None,
        "mean_get_clinic_slots_tokens_returned_per_call": (
            sum(all_obs_tokens) / len(all_obs_tokens) if all_obs_tokens else None),
        "mean_turns": sum(r["record"]["turns"] for r in rows) / total if total else None,
        "total_cost_usd": sum(r["record"]["cost_usd"] for r in rows),
        "wasted_get_clinic_slots_calls": wasted_gcs_calls,
        "guardrail_band_correct": "%d/%d" % (band_ok, total),
        "guardrail_correct_ordering": "%d/%d" % (order_ok, total),
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
    v1_rows = run_variant("v1_weak_get_clinic_slots", return_shape="verbose")
    v2_rows = run_variant("v2_full_get_clinic_slots", return_shape="compact")
    v1_summary = summarise(v1_rows, "v1_weak_get_clinic_slots")
    v2_summary = summarise(v2_rows, "v2_full_get_clinic_slots")

    out = {
        "tool_under_test": "get_clinic_slots",
        "model": config.MODEL,
        "case_subset": "book cases (1 trial) + no_slot_in_window escalate cases (3 trials) - only cases that call get_clinic_slots",
        "v1_weak_descriptor_and_verbose_return": v1_summary,
        "v2_full_descriptor_and_compact_return": v2_summary,
    }
    with open(os.path.join(OUT_DIR, "single_tool_ablation_get_clinic_slots.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)

    print()
    print("=" * 68)
    print("D2(b) single-tool ablation: get_clinic_slots (descriptor + return shape)")
    print("=" * 68)
    print("%-42s %10s %10s" % ("metric", "v1 weak", "v2 full"))
    print("%-42s %10.1f%% %9.1f%%" % ("pass rate", v1_summary["pass_rate"]*100, v2_summary["pass_rate"]*100))
    print("%-42s %10.1f%% %9.1f%%" % ("negative-case pass rate",
          (v1_summary["negative_pass_rate"] or 0)*100, (v2_summary["negative_pass_rate"] or 0)*100))
    print("%-42s %10.0f %10.0f" % ("avg tokens in (whole prompt)", v1_summary["mean_tokens_in"], v2_summary["mean_tokens_in"]))
    print("%-42s %10.1f %10.1f" % ("get_clinic_slots tokens RETURNED/call",
          v1_summary["mean_get_clinic_slots_tokens_returned_per_call"] or 0,
          v2_summary["mean_get_clinic_slots_tokens_returned_per_call"] or 0))
    print("%-42s %10.2f %10.2f" % ("avg turns", v1_summary["mean_turns"], v2_summary["mean_turns"]))
    print("%-42s $%9.4f $%9.4f" % ("total cost", v1_summary["total_cost_usd"], v2_summary["total_cost_usd"]))
    print("%-42s %10s %10s" % ("guardrail: band_correct", v1_summary["guardrail_band_correct"], v2_summary["guardrail_band_correct"]))
    print("%-42s %10s %10s" % ("guardrail: correct_ordering", v1_summary["guardrail_correct_ordering"], v2_summary["guardrail_correct_ordering"]))


if __name__ == "__main__":
    main()
