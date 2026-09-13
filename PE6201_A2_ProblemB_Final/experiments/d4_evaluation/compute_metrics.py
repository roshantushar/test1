#!/usr/bin/env python3
"""
D4 - EVALUATION METRICS, MAIN RESULTS TABLE, AND (optionally) LLM-AS-JUDGE
====================================================================
Two sources, selected with --source:

  scripted (default)  results/scripted/final_eval.json - free,
                       deterministic, reproducible with no key. Judge
                       column is populated by src/judge.py IF a key is
                       present, otherwise left "not run".
  live                 results/live/openai_gpt-4o-mini.json - the real
                       model's actual decision records (free-form
                       "reason" text worth judging). Needs a key to
                       populate the Judge column with src/judge.py
                       (a DIFFERENT model from the agent - see that
                       module's docstring).

Either way this script only READS already-produced result files and the
answer key (via harness.load_key - the one module allowed to) - it does
not run the agent itself.
====================================================================
"""
import argparse
import csv
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import config  # noqa: E402
import harness  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "evaluation")

SOURCES = {
    "scripted": os.path.join(HERE, "..", "..", "results", "scripted", "final_eval.json"),
    "live": os.path.join(HERE, "..", "..", "results", "live", "openai_gpt-4o-mini.json"),
}


def _is_negative(expected):
    return expected.get("expected_decision") in ("escalate", "request_information")


def build_rows(source):
    with open(SOURCES[source], encoding="utf-8") as fh:
        data = json.load(fh)
    key = harness.load_key()
    rows = []
    for r in data["results" if "results" in data else "trials"]:
        cid = r["case_id"]
        expected = key.get(cid)
        if expected is None:
            continue
        record = r["record"]
        # The OFFICIAL pass/fail definition (decision, trigger, missing,
        # booked, required/forbidden tools, book_slot count) - this is
        # what was reported everywhere else (STATUS.md, comparison.json)
        # and must not silently change here. code_check_breakdown adds
        # EXTRA diagnostic checks (e.g. "no unnecessary slot query") that
        # the assignment lists as separate, "also useful" metrics, NOT as
        # part of the pass gate - folding them in would quietly redefine
        # "pass" and mismatch the numbers already reported elsewhere.
        code_pass, _fails = harness.code_check(record, expected)
        breakdown = harness.code_check_breakdown(record, expected)
        rows.append({
            "case_id": cid, "trial": r["trial"], "family": expected.get("family"),
            "expected_decision": expected.get("expected_decision"),
            "actual_decision": record.get("decision"),
            "expected_trigger": expected.get("trigger"),
            "actual_trigger": record.get("trigger"),
            "expected_missing": expected.get("missing"),
            "actual_missing": record.get("missing"),
            "expected_booked": expected.get("booked"),
            "actual_booked": record.get("booked"),
            "turns": record.get("turns"),
            "reason": record.get("reason", ""),
            "evidence": record.get("evidence", []),
            "must_record": expected.get("must_record", []),
            "code_check_breakdown": breakdown,
            "code_check_pass": code_pass,
            "is_negative": _is_negative(expected),
            "judge_verdict": None, "judge_graded_by": None,
        })
    return rows


def maybe_run_judge(rows, run_judge):
    """Judge only trial==1 of each unique case (a judgement queue item
    per case, same convention as harness.run_set), to bound live cost."""
    if not run_judge:
        return rows
    if not config.API_KEY:
        print("  (skipping LLM-as-judge: no OPENROUTER_API_KEY - Judge column left 'not run')")
        return rows
    import judge as judge_mod
    seen = set()
    for row in rows:
        if row["trial"] != 1 or row["case_id"] in seen:
            continue
        seen.add(row["case_id"])
        item = {"case_id": row["case_id"], "decision": row["actual_decision"],
                "reason": row["reason"], "evidence": row["evidence"],
                "must_record": row["must_record"]}
        graded = judge_mod.judge_item(item)
        row["judge_verdict"] = graded["verdict"]
        row["judge_graded_by"] = graded["graded_by"]
        row["judge_notes"] = graded.get("notes")
        row["judge_detail"] = {
            "reason_supports_decision": graded.get("reason_supports_decision"),
            "evidence_meaningful": graded.get("evidence_meaningful"),
            "explanation_grounded": graded.get("explanation_grounded"),
            "must_record_satisfied": graded.get("must_record_satisfied"),
            "must_record": row["must_record"],
        }
        print("  [judge] %-10s -> %-4s  %s" % (row["case_id"], graded["verdict"], (graded.get("notes") or "")[:80]))
    return rows


def compute_metrics(rows):
    total = len(rows)
    passed = sum(1 for r in rows if r["code_check_pass"])
    negatives = [r for r in rows if r["is_negative"]]
    neg_passed = sum(1 for r in negatives if r["code_check_pass"])

    by_family = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in rows:
        fam = r["family"] or "(unlabelled)"
        by_family[fam]["total"] += 1
        if r["code_check_pass"]:
            by_family[fam]["passed"] += 1
    pass_rate_by_family = {fam: round(v["passed"] / v["total"], 4)
                           for fam, v in by_family.items()}

    # Counted across ALL rows, not just officially-failed ones: a wasted
    # get_clinic_slots call, for instance, can happen on a trial whose
    # FINAL decision/trigger was still correct (see the module docstring
    # above) - this tracks the diagnostic separately, per the
    # assignment's own "also useful" metrics list, without changing what
    # counts as an official pass.
    failure_types = Counter()
    for r in rows:
        for check, ok in r["code_check_breakdown"].items():
            if not ok:
                failure_types[check] += 1

    confusion = Counter((r["expected_decision"], r["actual_decision"]) for r in rows)

    turns = [r["turns"] for r in rows if r["turns"] is not None]
    unnecessary_slot_queries = sum(
        1 for r in rows if not r["code_check_breakdown"].get("no_unnecessary_slot_query", True))
    incorrect_bookings = sum(
        1 for r in rows if r["actual_decision"] == "book"
        and not r["code_check_breakdown"].get("booked_correct", True))

    judged = [r for r in rows if r["judge_verdict"] is not None]
    judge_pass_rate = (sum(1 for r in judged if r["judge_verdict"] == "PASS") / len(judged)
                       if judged else None)

    return {
        "trials": total,
        "overall_pass_rate": round(passed / total, 4) if total else None,
        "negative_trials": len(negatives),
        "negative_pass_rate": round(neg_passed / len(negatives), 4) if negatives else None,
        "pass_rate_by_family": pass_rate_by_family,
        "failure_count_by_check_type": dict(failure_types),
        "decision_confusion_counts": {"%s->%s" % k: v for k, v in confusion.items()},
        "avg_turns": round(statistics.mean(turns), 3) if turns else None,
        "median_turns": statistics.median(turns) if turns else None,
        "worst_case_turns": max(turns) if turns else None,
        "unnecessary_slot_queries": unnecessary_slot_queries,
        "incorrect_booking_count": incorrect_bookings,
        "judged_trials": len(judged),
        "judge_pass_rate": round(judge_pass_rate, 4) if judge_pass_rate is not None else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SOURCES), default="scripted")
    ap.add_argument("--judge", action="store_true",
                    help="run src/judge.py (a DIFFERENT model) against trial-1 of each case - needs a live key")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    rows = build_rows(args.source)
    rows = maybe_run_judge(rows, args.judge)
    metrics = compute_metrics(rows)

    manifest = [{"case_id": r["case_id"], "trial": r["trial"], "family": r["family"],
                "expected_decision": r["expected_decision"], "actual_decision": r["actual_decision"],
                "expected_trigger": r["expected_trigger"], "actual_trigger": r["actual_trigger"],
                "code_check_pass": r["code_check_pass"], "judge_verdict": r["judge_verdict"],
                "judge_notes": r.get("judge_notes"),
                "pass": r["code_check_pass"] and (r["judge_verdict"] in (None, "PASS"))}
               for r in rows]

    with open(os.path.join(OUT_DIR, "case_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    judge_rows = [{"case_id": r["case_id"], "reason": r["reason"], "verdict": r["judge_verdict"],
                  "graded_by": r.get("judge_graded_by"), "notes": r.get("judge_notes"),
                  "detail": r.get("judge_detail")}
                 for r in rows if r["trial"] == 1 and r["judge_verdict"] is not None]
    if judge_rows:
        with open(os.path.join(OUT_DIR, "judge_results_%s.json" % args.source), "w", encoding="utf-8") as fh:
            json.dump(judge_rows, fh, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "eval_set_summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": args.source, **metrics}, fh, indent=2, default=str)

    # Main results table (trial 1 of each case only, matching the
    # requested columns exactly).
    table_path = os.path.join(OUT_DIR, "main_results_table_%s.csv" % args.source)
    with open(table_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Case", "Family", "Expected", "Actual", "Trigger", "Code Check", "Judge", "Pass"])
        seen = set()
        for r in rows:
            if r["trial"] != 1 or r["case_id"] in seen:
                continue
            seen.add(r["case_id"])
            overall_pass = r["code_check_pass"] and (r["judge_verdict"] in (None, "PASS"))
            w.writerow([r["case_id"], r["family"], r["expected_decision"], r["actual_decision"],
                       r["actual_trigger"] or r["expected_trigger"] or "",
                       "PASS" if r["code_check_pass"] else "FAIL",
                       r["judge_verdict"] or "not run",
                       "PASS" if overall_pass else "FAIL"])

    print()
    print("=" * 68)
    print("D4 EVALUATION METRICS (source=%s)" % args.source)
    print("=" * 68)
    print(json.dumps(metrics, indent=2, default=str))
    print()
    print("Wrote:", os.path.join(OUT_DIR, "case_manifest.json"))
    print("      ", os.path.join(OUT_DIR, "eval_set_summary.json"))
    print("      ", table_path)


if __name__ == "__main__":
    main()
