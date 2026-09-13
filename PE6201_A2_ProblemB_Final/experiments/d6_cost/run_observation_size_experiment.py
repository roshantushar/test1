#!/usr/bin/env python3
"""
D6 - REQUIRED EXPERIMENT 3: observation size (verbose vs compact)
====================================================================
`get_clinic_slots` returns a list of {clinic, specialty, band, date,
time, capacity_remaining} dicts - one per free slot. `specialty` and
`band` are already known to the model (they are the arguments IT just
supplied to the call), and `capacity_remaining` is never used for
anything once the tool has already filtered to capacity>0 rows - see
tools.get_clinic_slots's own docstring. Repeating all three on every
row is pure observation bloat: this experiment measures what trimming
them costs and buys.

  verbose (shipped)   {clinic, specialty, band, date, time, capacity_remaining}
  compact             {clinic, date, time}                       - same rows, same order,
                                                                     only fields dropped

This is done via a LOCAL MONKEYPATCH of tools.REGISTRY["get_clinic_slots"]
inside this script only - src/tools.py itself is never edited, so the
shipped tool (and every other experiment/test that imports it) is
completely unaffected by this file existing.

CASE SELECTION: the 14 `book` cases (1 trial each) - the only cases in
the 45-case set that ever reach get_clinic_slots and see its
observation at all.
====================================================================
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import config  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "cost")


def _book_cases():
    from harness import load_cases, load_key
    key = load_key()
    cases = [c for c in load_cases() if c in key]
    return [c for c in cases if key[c].get("expected_decision") == "book"], key


def run_variant(label):
    import tools
    from harness import code_check
    from agent import run_case

    real_get_clinic_slots = tools.REGISTRY["get_clinic_slots"]

    def compact_get_clinic_slots(*a, **kw):
        rows = real_get_clinic_slots(*a, **kw)
        return [{"clinic": r["clinic"], "date": r["date"], "time": r["time"]} for r in rows]

    if label == "compact":
        tools.REGISTRY["get_clinic_slots"] = compact_get_clinic_slots

    try:
        cases, key = _book_cases()
        rows = []
        for cid in cases:
            expected = key[cid]
            record = run_case(cid)
            passed, fails = code_check(record, expected)
            rows.append({"case_id": cid, "passed": passed, "fails": fails, "record": record})
            print("  [%s] %-10s %-6s %s" % (label, cid, "PASS" if passed else "FAIL", record.get("decision")))
    finally:
        tools.REGISTRY["get_clinic_slots"] = real_get_clinic_slots

    return rows


def summarise(rows, label):
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    return {
        "label": label,
        "trials": total,
        "pass_rate": passed / total if total else None,
        "mean_tokens_in": sum(r["record"]["tokens_in"] for r in rows) / total if total else None,
        "mean_tokens_out": sum(r["record"]["tokens_out"] for r in rows) / total if total else None,
        "mean_turns": sum(r["record"]["turns"] for r in rows) / total if total else None,
        "total_cost_usd": sum(r["record"]["cost_usd"] for r in rows),
        "failures": [{"case_id": r["case_id"], "fails": r["fails"]} for r in rows if not r["passed"]],
    }


def main():
    if config.BACKEND != "live":
        sys.exit(
            "\n  This experiment needs config.BACKEND = 'live' and an API key.\n"
            "  Not run: BACKEND is %r in this environment (see STATUS.md).\n"
            % config.BACKEND)

    os.makedirs(OUT_DIR, exist_ok=True)
    verbose_rows = run_variant("verbose")
    compact_rows = run_variant("compact")
    verbose_summary = summarise(verbose_rows, "verbose")
    compact_summary = summarise(compact_rows, "compact")

    out = {
        "tool_under_test": "get_clinic_slots",
        "model": config.MODEL,
        "case_subset": "the 14 book cases (1 trial each) - the only cases that see this tool's observation",
        "verbose": verbose_summary,
        "compact": compact_summary,
        "token_saving_pct": round(
            100 * (1 - compact_summary["mean_tokens_in"] / verbose_summary["mean_tokens_in"]), 2
        ) if verbose_summary["mean_tokens_in"] else None,
    }
    with open(os.path.join(OUT_DIR, "d6_observation_size_experiment.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)

    print()
    print("=" * 68)
    print("D6 Experiment 3: observation size (get_clinic_slots)")
    print("=" * 68)
    print("%-20s %10s %10s" % ("metric", "verbose", "compact"))
    print("%-20s %9.1f%% %9.1f%%" % ("pass rate", verbose_summary["pass_rate"] * 100, compact_summary["pass_rate"] * 100))
    print("%-20s %10.0f %10.0f" % ("avg tokens in", verbose_summary["mean_tokens_in"], compact_summary["mean_tokens_in"]))
    print("%-20s %10.0f %10.0f" % ("avg tokens out", verbose_summary["mean_tokens_out"], compact_summary["mean_tokens_out"]))
    print("%-20s %10.2f %10.2f" % ("avg turns", verbose_summary["mean_turns"], compact_summary["mean_turns"]))
    print("%-20s $%9.4f $%9.4f" % ("total cost", verbose_summary["total_cost_usd"], compact_summary["total_cost_usd"]))
    print("token saving: %.2f%%" % out["token_saving_pct"])


if __name__ == "__main__":
    main()
