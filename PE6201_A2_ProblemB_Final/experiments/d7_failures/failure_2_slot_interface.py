#!/usr/bin/env python3
"""
D7 FAILURE 2 - TOOL INTERFACE FAILURE  (get_clinic_slots minus its band
safeguard) - a DIFFERENT layer from failure 1 (interface design, not
loop control). Scripted backend only.
====================================================================
THE WORKING INTERFACE (tools.get_clinic_slots): `band` is a REQUIRED
argument and every returned row is filtered to that exact band. An
agent cannot forget to check the band because the tool will not answer
without one, and it will never hand back a slot from the wrong band.

THE DELETION: a broken get_clinic_slots that ignores `band` entirely and
returns every slot for the specialty inside the date window, still
carrying each row's OWN band field. This is exactly the "band as an
optional filter" version the working scaffold explicitly warns against.

WHY THIS PRODUCES A WRONG BOOKING, NOT JUST A WRONG ANSWER THAT GETS
CAUGHT LATER: book_slot (this project's poka-yoke #2) only refuses a
booking that does not match a REAL row for the (clinic, date, time,
specialty, band) it is given. If the calling code takes `band` from the
tool's OWN returned row (a plausible thing for an agent to do once the
interface no longer forces band to come from the referral's assessed
urgency) rather than from check_referral_criteria's assessed band, that
row genuinely exists - so book_slot's cross-check PASSES, and a routine
patient is booked into an urgent slot that should have gone to an
urgent case. Two defences had to fail together for this to happen: the
interface safeguard (band required + filtered), and the calling
convention (band must come from the assessed urgency, never from a
slot's own label) - which is exactly why docs/D7_FAILURES.md argues this
belongs in the TOOL INTERFACE layer, not a guardrail or a prompt fix.

On REF-5602 (routine, window 2026-09-09 to 2026-11-04): the correct
booking is OPH-C2 on 2026-10-14. Two OPH slots dated inside that same
window are actually in the URGENT band (2026-09-15 and 2026-09-22,
OPH-C1) - reserved for genuinely urgent patients. With the safeguard
removed, the earliest-by-date pick grabs 2026-09-15, an urgent slot,
for a routine patient.
====================================================================
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import tools                        # noqa: E402
import backends                     # noqa: E402
from agent import run_case          # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "d7")
CASE = "REF-5602"


def _broken_get_clinic_slots(specialty, band=None, **window):
    """THE DELETION: band is optional and NOT filtered on at all."""
    lo = window.get("from", "0000-00-00")
    hi = window.get("to", "9999-99-99")
    return [dict(s) for s in tools._load("clinic_slots")
            if s["specialty"] == specialty
            and lo <= s["date"] <= hi
            and s["capacity_remaining"] > 0]


def _broken_moves(case_id):
    """A plausible agent built against the broken interface: it takes
    `band` for book_slot from the SLOT ROW itself (since the tool no
    longer insists band come from the assessed urgency), not from
    check_referral_criteria. Everything upstream of the slot search is
    identical to the real policy."""
    real = backends.ScriptedPolicyBackend(case_id)
    moves = real._derive_moves()   # the real, correct moves up to and including the search
    # Re-run the search step with the BROKEN tool, and re-decide the
    # booking call using the (wrong) row's own band.
    ref = tools.get_referral(case_id)
    crit = tools.check_referral_criteria(ref["specialty"], case_id)
    window = tools.compute_window(crit["window_weeks"])
    broken_slots = sorted(
        _broken_get_clinic_slots(ref["specialty"], **window),
        key=lambda s: (s["date"], s["time"]))
    chosen = broken_slots[0]

    fixed_moves = moves[:-2]   # keep everything up to (not including) the book turn + final
    fixed_moves.append({
        "thought": "Search for a free slot inside the window. (BROKEN: band "
                   "is not filtered - this may return the wrong band.)",
        "calls": [("get_clinic_slots", {"specialty": ref["specialty"],
                                        "from": window["from"], "to": window["to"]})]})
    fixed_moves.append({
        "thought": "Book the first slot found. (BROKEN: using the slot's OWN "
                   "band label, %r, instead of the assessed band %r.)"
                   % (chosen["band"], crit["band"]),
        "calls": [("book_slot", {"clinic": chosen["clinic"], "date": chosen["date"],
                                 "time": chosen["time"], "referral_id": case_id,
                                 "specialty": ref["specialty"], "band": chosen["band"]})]})
    fixed_moves.append({
        "thought": "Booked.",
        "final": {"decision": "book",
                  "booked": {"clinic": chosen["clinic"], "date": chosen["date"],
                            "time": chosen["time"]},
                  "reason": "(BROKEN RUN) booked without checking the band matched "
                            "the assessed urgency."}})
    return fixed_moves


def _run_with_patched_tool(fn, *args, **kwargs):
    real = tools.get_clinic_slots
    tools.REGISTRY["get_clinic_slots"] = _broken_get_clinic_slots
    tools.get_clinic_slots = _broken_get_clinic_slots
    try:
        return fn(*args, **kwargs)
    finally:
        tools.get_clinic_slots = real
        tools.REGISTRY["get_clinic_slots"] = real


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    before = run_case(CASE)

    broken = _run_with_patched_tool(run_case, CASE, force_moves=_broken_moves(CASE))

    restored = run_case(CASE)

    correct_booking = {"clinic": "OPH-C2", "date": "2026-10-14", "time": "11:20"}
    unsafe_booking = (broken.get("decision") == "book"
                      and broken.get("booked") != correct_booking)

    out = {
        "failure": "tool_interface - get_clinic_slots' band safeguard removed",
        "layer": "tool interface (tools.py: get_clinic_slots)",
        "method": "working interface minus X (band filtering), X restored",
        "before": {"decision": before["decision"], "booked": before.get("booked"),
                   "turns": before["turns"], "tool_calls": before["tool_call_count"],
                   "tokens_total": before["tokens_in"] + before["tokens_out"],
                   "cost_usd": before["cost_usd"], "stopped_by": before["stopped_by"]},
        "broken": {"decision": broken["decision"], "booked": broken.get("booked"),
                  "turns": broken["turns"], "tool_calls": broken["tool_call_count"],
                  "tokens_total": broken["tokens_in"] + broken["tokens_out"],
                  "cost_usd": broken["cost_usd"], "stopped_by": broken["stopped_by"]},
        "restored": {"decision": restored["decision"], "booked": restored.get("booked"),
                    "turns": restored["turns"], "tool_calls": restored["tool_call_count"],
                    "tokens_total": restored["tokens_in"] + restored["tokens_out"],
                    "cost_usd": restored["cost_usd"], "stopped_by": restored["stopped_by"]},
        "correct_booking": correct_booking,
        "unsafe_booking": unsafe_booking,
        "why_the_other_two_layers_are_the_wrong_place": (
            "The step cap and budget ceiling bound RUN LENGTH; this run is "
            "short (5 turns) and cheap, so neither would ever fire - they "
            "cannot detect a wrong but confidently-reached answer. Action "
            "de-duplication does not apply either: nothing is repeated. Only "
            "the tool interface (making band mandatory AND filtered, so a "
            "wrong-band row can never be returned in the first place) closes "
            "this - the same reasoning that made band a required argument on "
            "get_clinic_slots and specialty+band required, cross-checked "
            "arguments on book_slot in the working version."),
        "restored_matches_before": (
            restored["decision"] == before["decision"]
            and restored.get("booked") == before.get("booked")),
    }

    with open(os.path.join(OUT_DIR, "failure_2_slot_interface.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
