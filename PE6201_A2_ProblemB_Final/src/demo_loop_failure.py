#!/usr/bin/env python3
"""
PE6201 A2 Problem B (Final) - D7 FAILURE #1: the loop-control failure
====================================================================
    python3 src/demo_loop_failure.py

Follows the method shown in the scaffold (A2_scaffold 2/demo_loop_failure.py):
D7 requires each failure to be built as "the working agent, minus X", not
a separately written bad agent - and restoring X must recover the
behaviour. Here X is ACTION DE-DUPLICATION (guardrails.py). Everything
else is untouched, including tools.py and the reference-solver backend.

See experiments/d7_failures/ for the fuller before/broken/restored
write-up (both failures) with saved evidence under results/d7/.
====================================================================
"""
import copy

import config
from agent import run_case
from guardrails import Guardrails

CASE = "REF-5602"


def _looping_moves(case_id):
    """The working, real move list for CASE, with one call repeated -
    modelling a model that has forgotten it already asked."""
    import backends
    real = backends.ScriptedPolicyBackend(case_id)._derive_moves()
    repeat = copy.deepcopy(real[1])   # the check_referral_criteria/lookup_patient turn
    repeat["thought"] = "Let me check the criteria again to be sure."
    return real[:2] + [repeat, repeat] + real[2:]


def main():
    print()
    print(config.summary())
    print("  demonstrating on %s" % CASE)
    print()

    before = run_case(CASE)
    print("BEFORE - the working agent, guard in place")
    print("  turns %d . tool calls %d . tokens %d . cost US$%.5f . decision %s"
          % (before["turns"], before["tool_call_count"],
             before["tokens_in"] + before["tokens_out"],
             before["cost_usd"], before["decision"]))

    real_check = Guardrails.check_duplicate
    Guardrails.check_duplicate = lambda self, tool, args: None   # <- the deletion
    try:
        after = run_case(CASE, force_moves=_looping_moves(CASE))
    finally:
        Guardrails.check_duplicate = real_check                  # <- put it back

    print()
    print("AFTER - the working agent MINUS action de-duplication")
    print("  turns %d . tool calls %d . tokens %d . cost US$%.5f . decision %s"
          % (after["turns"], after["tool_call_count"],
             after["tokens_in"] + after["tokens_out"],
             after["cost_usd"], after["decision"]))
    print("  stopped by: %s" % after["stopped_by"])

    spend = ((after["tokens_in"] + after["tokens_out"])
             / max(1, before["tokens_in"] + before["tokens_out"]))
    print()
    print("=" * 68)
    print("  1 - THE INSTRUMENTATION THAT FOUND IT")
    print("      turns and cost logged per run. NOTHING RAISED AN EXCEPTION.")
    print("      The run cost %.1fx more and still answered %r"
          % (spend, after["decision"]))
    if after["decision"] == before["decision"]:
        print("      - THE SAME ANSWER. A pass-rate table alone would show")
        print("      this as a clean pass; only turns/cost expose it.")
    print("  2 - THE TURN DISTRIBUTION")
    print("      before: %d turns   after: %d turns   cap: %d"
          % (before["turns"], after["turns"], config.MAX_TURNS))
    print("  3 - THE FIX, AND WHY THE OTHER TWO LAYERS WERE WRONG")
    print("      Action de-duplication catches it, in the CODE layer.")
    if after["stopped_by"] != "step_cap":
        print("      The step cap never fired: %d turns is inside the cap of %d."
              % (after["turns"], config.MAX_TURNS))
    print("      Budget ceiling: %d tokens against a ceiling of %d - did not fire."
          % (after["tokens_in"] + after["tokens_out"], config.MAX_TOKENS_PER_RUN))
    print("  4 - RESTORED: passing the guard back in returns turn/cost/decision")
    print("      to the BEFORE numbers exactly - see results/d7/failure_1_loop.json.")
    print("=" * 68)
    print()
    return before, after


if __name__ == "__main__":
    main()
