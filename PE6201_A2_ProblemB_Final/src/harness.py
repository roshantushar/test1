"""
PE6201 A2 Problem B (Final) - THE HARNESS  (D4, D5)
====================================================================
Load the answer key, run cases, grade them, report.

GROUND-TRUTH FIREWALL: this is the ONLY module in this project that
opens expected_outcomes_B.json. agent.py, tools.py, backends.py and
prompt.py never do.

TWO KINDS OF CHECK, reused from the scaffold's approach
(A2_scaffold 2/harness.py):

  CODE CHECK        decision == expected_decision, plus trigger / missing
                    / booked / required-and-forbidden tools / book_slot
                    count. Deterministic, free, instant.
  JUDGEMENT CHECK   builds a queue for a person (or a declared second
                    model) to rule on: is the reason grounded, is the
                    evidence meaningful, is every `must_record` item
                    actually present. This harness does NOT automate
                    that ruling - see docs/D4_EVALUATION.md for why.

TRIAL POLICY (D4): ordinary cases get 1 trial per model; NEGATIVE cases
(escalate / request_information) get 3, because a single trial cannot
tell a real refusal from a lucky one. On the deterministic scripted
backend the three trials of a negative case are identical by
construction (no randomness) - the point of 3 trials is realised on the
LIVE battery, where a model can answer differently across trials; the
scripted run keeps the same trial policy for consistency and so the
report format never has to change between backends.
====================================================================
"""
import json
import os
import statistics

import config
from agent import run_case


# =====================================================================
# LOADING
# =====================================================================
def load_key():
    with open(config.expected_outcomes_path(), encoding="utf-8") as fh:
        rows = json.load(fh)
    return {r["case_id"]: r for r in rows}


def load_cases():
    with open(os.path.join(config.data_b_dir(), "referrals.json"), encoding="utf-8") as fh:
        return [r["referral_id"] for r in json.load(fh)]


# =====================================================================
# THE CODE CHECK
# =====================================================================
_REQUIRED_TOOLS_FOR = {
    "book": {"get_referral", "check_referral_criteria", "lookup_patient",
             "compute_window", "get_clinic_slots", "book_slot"},
}
_FORBIDDEN_IF_NOT_BOOK = {"book_slot"}


def code_check(record, expected):
    """Deterministic comparison. Returns (passed, [reasons]).

    Compares: the decision, the single trigger (for an escalation), the
    missing item (for a request), the booked clinic/date/time (for a
    booking), whether book_slot was called an appropriate number of
    times, and whether the tools required for that outcome were actually
    called. Wording, turn count and cost are NOT compared - those are
    D2(c)/D6 concerns, not correctness.
    """
    fails = []
    dec, exp_dec = record.get("decision"), expected.get("expected_decision")
    if dec != exp_dec:
        fails.append("decision %r, expected %r" % (dec, exp_dec))

    if expected.get("trigger"):
        if record.get("trigger") != expected["trigger"]:
            fails.append("trigger %r, expected %r" % (record.get("trigger"), expected["trigger"]))

    if expected.get("missing"):
        got = (record.get("missing") or "")
        want = expected["missing"]
        # loose containment: the code the test names must appear.
        code = want.split()[-1]
        if code not in got and want not in got:
            fails.append("missing %r does not name %r" % (got, want))

    if expected.get("booked"):
        got = record.get("booked") or {}
        # A weak live model can put "booked" as something other than a
        # {clinic, date, time} dict - e.g. a bare list - observed on
        # meta-llama/llama-3.1-8b-instruct. Treat any non-dict shape as
        # simply missing the fields it should have had, rather than
        # crashing the whole harness on a malformed live reply.
        if not isinstance(got, dict):
            fails.append("booked %r is not a {clinic,date,time} object" % (got,))
            got = {}
        for field in ("clinic", "date", "time"):
            if got.get(field) != expected["booked"][field]:
                fails.append("booked.%s %r, expected %r"
                             % (field, got.get(field), expected["booked"][field]))

    called = {e["tool"] for e in record.get("evidence", [])}
    book_calls = sum(1 for e in record.get("evidence", []) if e["tool"] == "book_slot")

    if exp_dec == "book":
        missing_tools = _REQUIRED_TOOLS_FOR["book"] - called
        if missing_tools:
            fails.append("required tool(s) never called: %s" % ", ".join(sorted(missing_tools)))
        if book_calls != 1:
            fails.append("book_slot called %d times, expected exactly 1" % book_calls)
    else:
        if book_calls != 0:
            fails.append("book_slot called %d times, expected 0 for a %s decision"
                         % (book_calls, exp_dec))

    return (not fails), fails


def code_check_breakdown(record, expected):
    """Per-check granularity, for D4's metrics report (failure count BY
    CASE TYPE, decision confusion counts, etc.) - `code_check` above
    remains the pass/fail-plus-reasons interface every other caller uses;
    this is additive, not a replacement."""
    dec, exp_dec = record.get("decision"), expected.get("expected_decision")
    called = {e["tool"] for e in record.get("evidence", [])}
    book_calls = sum(1 for e in record.get("evidence", []) if e["tool"] == "book_slot")

    checks = {"decision_correct": dec == exp_dec}

    if expected.get("trigger"):
        checks["trigger_correct"] = record.get("trigger") == expected["trigger"]
    if expected.get("missing"):
        got = record.get("missing") or ""
        want = expected["missing"]
        code = want.split()[-1]
        checks["missing_correct"] = code in got or want in got
    if expected.get("booked"):
        got = record.get("booked") or {}
        if not isinstance(got, dict):
            got = {}
        checks["booked_correct"] = all(
            got.get(f) == expected["booked"][f] for f in ("clinic", "date", "time"))

    if exp_dec == "book":
        checks["required_tools_present"] = not (_REQUIRED_TOOLS_FOR["book"] - called)
        checks["book_slot_fired_correctly"] = book_calls == 1
    else:
        checks["forbidden_tool_absent"] = book_calls == 0

    # unnecessary slot query: get_clinic_slots called on a case that
    # should never have reached a slot search at all (anything that is
    # NOT book and NOT the no_slot_in_window family, which legitimately
    # calls it and finds nothing).
    should_never_query = exp_dec != "book" and expected.get("trigger") != "no_slot_in_window"
    checks["no_unnecessary_slot_query"] = not (should_never_query and "get_clinic_slots" in called)

    return checks


# =====================================================================
# THE JUDGEMENT CHECK
# =====================================================================
def prepare_judgement_check(record, expected):
    """Build ONE item for a human (or a declared second model) to rule
    on. Does NOT decide anything itself - must_record items are English
    sentences, and a substring match would be theatre. See src/judge.py
    for the (separate-model) LLM-as-judge implementation that can fill
    in `verdict`/`graded_by` when a live key is available."""
    return {
        "case_id": record["case_id"],
        "decision": record.get("decision"),
        "reason": record.get("reason", ""),
        "evidence": record.get("evidence", []),
        "must_record": expected.get("must_record", []),
        "verdict": None,
        "graded_by": None,
    }


# =====================================================================
# RUNNING THE SET
# =====================================================================
def _is_negative(expected):
    if not expected:
        return False
    return expected.get("expected_decision") in ("escalate", "request_information")


def run_set(case_ids=None, trials_for=None, verbose=False, descriptor_version="v2",
            parallel=True):
    key = load_key()
    case_ids = case_ids or load_cases()
    trials_for = trials_for or (lambda cid: 3 if _is_negative(key.get(cid)) else 1)

    results, judgement_queue = [], []
    for cid in case_ids:
        expected = key.get(cid)
        if expected is None:
            print("  SKIP %s - no label in the answer key" % cid)
            continue
        for trial in range(1, trials_for(cid) + 1):
            record = run_case(cid, verbose=verbose, parallel=parallel,
                              descriptor_version=descriptor_version)
            passed, fails = code_check(record, expected)
            results.append({"case_id": cid, "trial": trial, "passed": passed,
                            "fails": fails, "record": record,
                            "family": expected.get("family")})
            if trial == 1:
                judgement_queue.append(prepare_judgement_check(record, expected))
    return results, judgement_queue


# =====================================================================
# REPORTING
# =====================================================================
def report(results):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    turns = [r["record"]["turns"] for r in results]
    cost = sum(r["record"]["cost_usd"] for r in results)

    print()
    print("=" * 68)
    print("  RESULTS   %d of %d trials passed   (%.0f%%)"
          % (passed, total, 100.0 * passed / total if total else 0))
    print("=" * 68)
    print("  trials              %d" % total)
    print("  median turns        %s" % (statistics.median(turns) if turns else "-"))
    print("  worst case turns    %s" % (max(turns) if turns else "-"))
    print("  hit the step cap    %d"
          % sum(1 for r in results if r["record"]["stopped_by"] == "step_cap"))
    print("  total cost          US$%.4f   (%s backend)"
          % (cost, results[0]["record"]["backend"] if results else "-"))
    print()

    failures = [r for r in results if not r["passed"]]
    if failures:
        print("  FAILED TRIALS:")
        for r in failures:
            print("    %-12s trial %d  [%s]" % (r["case_id"], r["trial"], r["family"]))
            for f in r["fails"]:
                print("        %s" % f)
    else:
        print("  Every trial passed the code check.")
        print("  That is HALF the check - see the judgement queue.")
    print()
    return {"trials": total, "passed": passed,
            "pass_rate": passed / total if total else 0.0,
            "median_turns": statistics.median(turns) if turns else None,
            "cost_usd": cost}
