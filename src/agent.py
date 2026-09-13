"""
PE6201 A2 Problem B (Final) - THE AGENT LOOP  (D1)
====================================================================
    thought -> action/tool call(s) -> observation(s) -> repeat -> final

Hand-rolled, following the scaffold's approach (A2_scaffold 2/agent.py):
no framework owns the loop, so a misbehaving run can be read line by
line. What makes this an AGENT rather than a fixed workflow: the number
of turns and which tools are called is decided by the DATA a case
returns (see backends.ScriptedPolicyBackend and docs/D0_AGENT_JUSTIFICATION.md),
not hard-coded per case.

INSTRUMENTATION IS NOT OPTIONAL (D1, D6, D7). Every run records case_id,
backend, model, turns, tool calls, tokens in/out, cost, runtime,
guardrail events, the full evidence trace, the final decision (and its
trigger / missing item / booking), and stopped_by.
====================================================================
"""
import time

import config
import prompt
import tools
from backends import _find_duplicate, make_backend
from decision_log import record_decision
from guardrails import Guardrails, GuardrailStop


def run_case(case_id, approve=None, verbose=False, parallel=True,
             descriptor_version="v2", force_moves=None, system_prompt_override=None):
    """Run ONE case from a clean state and return the decision record.

    ISOLATION (D4): everything needed is created inside this call - no
    module-level counters, no shared guardrail instance, no leftover
    transcript between cases.

    `parallel`  passed to the scripted backend: True groups independent
                calls into one turn (the default, used for the real
                evaluation set); False forces one call per turn, used
                only by the D2(c) sequential-vs-parallel comparison.
    `descriptor_version`  "v1" or "v2" - only affects the LIVE backend's
                system prompt (see prompt.py); ignored by the scripted
                backend, which never sends a prompt to anything. Ignored
                when `system_prompt_override` is given.
    `force_moves`  used only by D7's loop-failure demo, to replay a
                transcript with an injected repeated call.
    `system_prompt_override`  a fully-assembled system prompt string,
                used only by D2(b)'s single-tool descriptor ablation
                (see prompt.build_system_prompt_single_tool_swap) - lets
                that experiment vary ONE tool's descriptor while every
                other prompt component stays exactly at v2.
    """
    started = time.time()

    guards = Guardrails(config.MAX_TURNS, config.MAX_TOKENS_PER_RUN, config.AUTONOMY)
    system_prompt = system_prompt_override or prompt.build_system_prompt(descriptor_version)
    backend = make_backend(case_id, system_prompt=system_prompt,
                            parallel=parallel, force_moves=force_moves)

    # Seed the transcript with the one fact that is not in the system
    # prompt: WHICH referral this run is about. The scripted backend
    # ignores `transcript` entirely (it already knows case_id directly -
    # see backends.ScriptedPolicyBackend), so this only matters on the
    # live backend - but without it, a live model has no way to know
    # which id to pass to get_referral, and every live run silently
    # fails to resolve turn 1. Caught by testing against a real API call.
    transcript = [{"role": "user",
                   "content": "Handle referral %s." % case_id}]
    evidence = []        # every tool actually called, in order, with its args
    last_result = {}     # tool name -> its most recent return value, for the
                          # duplicate-check enforcement below

    # TURNS ARE TOOL-CALLING TURNS. The concluding move (writing the
    # decision) is bookkeeping, not a turn - consistent with the
    # scaffold's convention and with Appendix A's worked examples.
    turns = 0
    iterations = 0        # loop-safety only, never reported
    tokens_in = tokens_out = 0
    stopped_by = None
    record = None

    if approve is None:
        # Auto-approve so the scripted run stays deterministic. The
        # RECORD still shows the gate was reached and passed.
        approve = lambda action, payload: True

    def _verified_book_slot(args, observations=None):
        """THE ONE PLACE book_slot IS EVER ACTUALLY CALLED - whether the
        model called it as a tool itself, or (see the "final" handling
        below) merely DECLARED a booking without calling it. Centralising
        this is what lets poka-yoke #3 (the duplicate-check enforcement)
        apply identically either way, rather than being bypassable by a
        model that skips the tool call and just asserts the outcome.

        Returns the book_slot result dict. Raises GuardrailStop if the
        gate holds, a real unverified duplicate is found, or this run
        already booked successfully once before (guardrail #6 -
        SINGLE-BOOKING: action de-duplication alone would not catch a
        SECOND, DIFFERENT booking attempt).
        """
        guards.check_single_booking(bool(last_result.get("book_slot", {}).get("booked")))

        # A weak live model can call book_slot with an incomplete args
        # dict (missing clinic/date/time/etc.) - observed on
        # meta-llama/llama-3.1-8b-instruct, which crashed the run with a
        # TypeError from tools.call's **args unpacking. Validate the
        # required keys are present BEFORE calling the real tool, and
        # raise a recognisable GuardrailStop instead of letting a single
        # malformed call take down the whole evaluation.
        required = {"clinic", "date", "time", "referral_id", "specialty", "band"}
        missing = required - set(args or {})
        if missing:
            raise GuardrailStop(
                "invalid_tool_args",
                "book_slot called with missing required args: %s" % sorted(missing))
        # A weak live model can also pass EXTRA keys book_slot's signature
        # does not accept (e.g. a "capacity" field copied from a
        # get_clinic_slots row) - observed on
        # meta-llama/llama-3.1-8b-instruct, crashing tools.call's **args
        # unpacking with a TypeError. All six required keys are already
        # confirmed present above, so dropping any extras is safe: it
        # changes nothing about WHICH slot is being booked.
        args = {k: args[k] for k in required}

        referral = last_result.get("get_referral") or {}
        patient_id, specialty = referral.get("patient_id"), args.get("specialty")
        already_checked = any(e["tool"] == "lookup_patient" for e in evidence)
        if patient_id and specialty:
            if already_checked:
                dup_result = last_result.get("lookup_patient")
            else:
                dup_result = tools.call("lookup_patient", {"patient_id": patient_id})
                dup_args = {"patient_id": patient_id}
                evidence.append({"tool": "lookup_patient", "args": dup_args,
                                "observation": dup_result, "auto_injected": True})
                if observations is not None:
                    observations.append({"tool": "lookup_patient", "args": dup_args,
                                         "observation": dup_result, "auto_injected": True})
                last_result["lookup_patient"] = dup_result
                if verbose:
                    print("       %-26s -> %s   (AUTO-INJECTED: "
                          "duplicate check before book_slot)"
                          % ("lookup_patient", _short(dup_result)))
            dup = _find_duplicate(dup_result, specialty) if dup_result else None
            guards.check_no_unverified_duplicate(dup, specialty)

        if not guards.gate("book_slot", args, approve):
            raise GuardrailStop(
                "gate_held", "book_slot awaits human approval (autonomy=%s)"
                            % config.AUTONOMY)

        result = tools.call("book_slot", args)
        evidence.append({"tool": "book_slot", "args": args, "observation": result})
        if observations is not None:
            observations.append({"tool": "book_slot", "args": args, "observation": result})
        last_result["book_slot"] = result
        if verbose:
            print("       %-26s -> %s" % ("book_slot", _short(result)))
        return result

    try:
        while True:
            iterations += 1
            if iterations > config.MAX_TURNS + 2:
                raise GuardrailStop("step_cap", "loop did not terminate")

            move = backend.next_move(transcript)
            ti, to = backend.token_estimate(transcript)
            tokens_in, tokens_out = tokens_in + ti, tokens_out + to
            guards.check_budget(tokens_in + tokens_out)

            # A live model's "calls" entries are usually [name, args]
            # pairs (as the prompt asks), but can also arrive as
            # {"name"/"tool": ..., "args": ...} objects - observed under
            # the deliberately vague v1 prompt, which never pins down
            # the exact pair shape. Normalise every entry to a (name,
            # args) tuple in ONE place, before anything else indexes
            # into it, rather than crashing wherever the first raw index
            # happens to be.
            if move.get("calls"):
                normalized = []
                malformed = False
                for entry in move["calls"]:
                    if isinstance(entry, (list, tuple)) and len(entry) == 2:
                        normalized.append(tuple(entry))
                    elif isinstance(entry, dict) and ("name" in entry or "tool" in entry):
                        normalized.append((entry.get("name") or entry.get("tool"),
                                          entry.get("args", {})))
                    else:
                        malformed = True
                        break
                if malformed:
                    move = {"final": {"decision": "escalate",
                                      "reason": "a 'calls' entry matched neither "
                                                "the [name, args] pair shape nor "
                                                "a {name/tool, args} object: %r"
                                                % (entry,),
                                      "trigger": "malformed_agent_output"}}
                else:
                    move["calls"] = normalized

            # A live model can conclude by "calling" a pseudo-tool named
            # after the DECISION itself - e.g. {"calls":
            # [["request_information", {"missing": "visual field test
            # VF-01"}]]} - instead of using the "final" shape, even
            # though it derived the exact right value (observed
            # reproducibly on openai/gpt-4o-mini, REF-5614 - see
            # STATUS.md). This is an unambiguous shape confusion, not a
            # reasoning error: reinterpret it as the "final" move it
            # clearly meant, rather than either fabricating a value or
            # failing a correct answer over its shape.
            if (move.get("calls") and len(move["calls"]) == 1
                    and move["calls"][0][0] in ("book", "request_information", "escalate")):
                dec_name, dec_args = move["calls"][0]
                move = {"thought": move.get("thought", ""),
                       "final": dict(dec_args, decision=dec_name)}

            if verbose:
                label = "conclude" if "final" in move else "turn %d" % (turns + 1)
                print("  %-9s . %s" % (label, move.get("thought", "")[:88]))

            if "final" in move:
                record = dict(move["final"])
                # A live model can name the booking with clinic/date/time
                # as TOP-LEVEL keys in "final" instead of nesting them
                # under "booked", despite the prompt asking for the
                # nested shape (observed on openai/gpt-4o-mini - see
                # STATUS.md). Normalise that ONE harmless formatting
                # variant rather than failing a correct booking over it;
                # this does not touch or invent any value, it only
                # regroups keys the model already provided.
                if (record.get("decision") == "book" and not record.get("booked")
                        and {"clinic", "date", "time"} <= set(record)):
                    record["booked"] = {"clinic": record["clinic"],
                                        "date": record["date"],
                                        "time": record["time"]}

                # A live model can also omit "booked" ENTIRELY - not
                # flattened, just absent - when nothing in its prompt
                # told it the field is expected (observed under the
                # minimal v1 answer format, which states the JSON shapes
                # but not every field name). If book_slot was ALREADY
                # called this run and genuinely succeeded, backfill
                # "booked" from that real result rather than failing a
                # correct, completed booking over a missing field in the
                # write-up - this reads back a fact already on record, it
                # invents nothing.
                if (record.get("decision") == "book" and not record.get("booked")
                        and last_result.get("book_slot", {}).get("booked")):
                    b = last_result["book_slot"]
                    record["booked"] = {"clinic": b["clinic"], "date": b["date"],
                                        "time": b["time"]}

                # FOURTH POKA-YOKE: a live model can declare
                # "decision": "book" without ever having CALLED book_slot
                # - it reasoned correctly (found a real slot) but simply
                # asserted the outcome in prose instead of performing the
                # tool call the prompt explicitly requires (observed on
                # openai/gpt-4o-mini, e.g. REF-6001 - see STATUS.md). The
                # same principle as the duplicate-check poka-yoke applies:
                # never accept a claimed irreversible action as having
                # happened - either complete it for real (still through
                # the same gate and the same duplicate check), or refuse
                # to report it as booked. This can only ever CONFIRM a
                # booking that is independently verified against the real
                # slot table (tools.book_slot's own poka-yoke #2) - it can
                # never fabricate one.
                already_booked = any(e["tool"] == "book_slot" for e in evidence)
                if (record.get("decision") == "book" and not already_booked
                        and record.get("booked")):
                    booked = record["booked"]
                    referral = last_result.get("get_referral") or {}
                    crit = last_result.get("check_referral_criteria") or {}
                    specialty, band = referral.get("specialty"), crit.get("band")
                    # A weak live model can put "booked" as something
                    # other than a {clinic, date, time} dict - e.g. a
                    # bare list - the same malformed shape already
                    # guarded against in harness.code_check. Treat any
                    # non-dict shape as nothing usable to verify, rather
                    # than crashing on .get().
                    if (isinstance(booked, dict) and booked.get("clinic")
                            and booked.get("date") and booked.get("time")
                            and specialty and band):
                        args = {"clinic": booked["clinic"], "date": booked["date"],
                                "time": booked["time"], "referral_id": case_id,
                                "specialty": specialty, "band": band}
                        if verbose:
                            print("       %-26s    (model declared this booking "
                                  "without calling the tool - verifying for real)"
                                  % "book_slot")
                        result = _verified_book_slot(args)
                        if result.get("booked"):
                            record["booked"] = {"clinic": result["clinic"],
                                                "date": result["date"],
                                                "time": result["time"]}
                        else:
                            record["decision"] = "escalate"
                            record["trigger"] = "booking_failed"
                            record["reason"] = ("model declared a booking that "
                                                "could not be verified: %s"
                                                % result.get("error"))
                    else:
                        # Declared "book" but we cannot even identify
                        # which specialty/band it means - too little to
                        # safely complete the action, so it is refused
                        # rather than guessed at.
                        record["decision"] = "escalate"
                        record["trigger"] = "booking_not_verified"
                        record["reason"] = ("model declared \"decision\": \"book\" "
                                            "without ever calling book_slot, and "
                                            "not enough context was available to "
                                            "verify or complete it safely")
                break

            # A live model's reply can be syntactically valid JSON that
            # still matches neither of the two documented shapes (no
            # "final", no "calls", and no top-level "tool"/"args" pair
            # either - e.g. it answered in prose fields of its own
            # invention). Treat that as a loud, recorded failure instead
            # of crashing the run on a KeyError.
            if move.get("calls"):
                calls = move["calls"]
            elif "tool" in move and "args" in move:
                calls = [(move["tool"], move["args"])]
            else:
                record = {"decision": "escalate",
                          "reason": "model reply matched neither the 'calls' "
                                    "nor the 'final' shape: %r" % (move,),
                          "trigger": "malformed_agent_output"}
                break

            turns += 1
            guards.check_turns(turns)
            observations = []

            for name, args in calls:
                if not isinstance(args, dict):
                    # A live model can call a tool with non-dict args (a
                    # bare string, a list, ...) - observed under the
                    # deliberately vague v1 prompt, which (unlike v2)
                    # never states args must be a JSON object. Every
                    # downstream check (guards.check_duplicate,
                    # tools.call) assumes a dict; validate BEFORE any of
                    # them run rather than crashing on whichever happens
                    # to be first.
                    raise GuardrailStop(
                        "invalid_tool_args",
                        "model called %r with non-dict args: %r" % (name, args))
                guards.check_duplicate(name, args)

                if name == tools.GATED_ACTION:
                    # THIRD POKA-YOKE, via the shared _verified_book_slot
                    # helper: a booking may never complete without a
                    # duplicate-appointment check having actually happened
                    # THIS run, regardless of whether the model remembered
                    # to call lookup_patient - see that helper's docstring.
                    _verified_book_slot(args, observations)
                    continue

                if name not in tools.REGISTRY:
                    # A live model can hallucinate a tool name that does
                    # not exist - observed on openai/gpt-4o-mini calling
                    # "request_information" (one of the three DECISIONS,
                    # not a tool) instead of concluding with "final".
                    # tools.call() raises KeyError loudly by design (see
                    # its docstring) for exactly this reason, but a
                    # single hallucinated name must not crash the whole
                    # evaluation run - record it as a loud, recognisable
                    # failure and stop this case instead.
                    raise GuardrailStop(
                        "invalid_tool_call",
                        "model called a tool named %r, which does not exist "
                        "(available: %s)" % (name, ", ".join(sorted(tools.REGISTRY))))

                try:
                    result = tools.call(name, args)
                except (TypeError, ValueError) as e:
                    # A live model can also call a REAL tool with the
                    # wrong argument names/count (a TypeError from
                    # Python's own keyword-argument binding) or with a
                    # value a tool's own validation rejects - e.g.
                    # compute_window(window_weeks=None), observed on
                    # meta-llama/llama-3.1-8b-instruct, which raises
                    # ValueError by design (see tools.py). Same treatment
                    # as an unknown tool name: a loud, recorded stop, not
                    # a crash that takes down the whole evaluation run.
                    raise GuardrailStop(
                        "invalid_tool_args",
                        "model called %s(%r) with arguments that do not "
                        "match its signature or fail its own validation: %s"
                        % (name, args, e))
                evidence.append({"tool": name, "args": args, "observation": result})
                observations.append({"tool": name, "args": args, "observation": result})
                last_result[name] = result
                if verbose:
                    print("       %-26s -> %s" % (name, _short(result)))

                # GUARDRAIL #7 (monthly limit per caller): checked as
                # early as possible - the instant get_referral resolves
                # the caller's identity (the referring clinic), before
                # any further tool call this run. Cross-run state, not
                # per-run - see guardrails.py's module-level counter.
                if name == "get_referral" and result:
                    guards.check_monthly_limit(
                        result.get("referring_clinic", "(unknown caller)"),
                        config.MAX_MONTHLY_REQUESTS_PER_CALLER)

            transcript.append({"role": "assistant", "content": move.get("thought", "")})
            transcript.append({"role": "user", "content": repr(observations)})

    except GuardrailStop as stop:
        stopped_by = stop.reason
        # unverified_duplicate is not a generic system fault like
        # step_cap/budget_ceiling/duplicate_action - it IS one of the
        # five canonical routing triggers (see prompt.RULES), just
        # detected by the agent's own orchestration instead of the
        # model. Report it under its real business name so the code
        # check recognises it exactly as it would if the model itself
        # had escalated for the same reason.
        trigger = ("duplicate_future_appointment" if stop.reason == "unverified_duplicate"
                  else "guardrail_%s" % stop.reason)
        record = {"decision": "escalate",
                  "reason": "halted by the %s guardrail - %s" % (stop.reason, stop.detail),
                  "trigger": trigger}

    cost = (tokens_in / 1e6) * config.PRICE_IN + (tokens_out / 1e6) * config.PRICE_OUT

    record.update({
        "case_id": case_id,
        "backend": config.BACKEND,
        "model": config.MODEL if config.BACKEND == "live" else "(scripted policy)",
        "descriptor_version": descriptor_version,
        "evidence": evidence,
        "tool_call_count": len(evidence),
        "turns": turns,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(cost, 6),
        "seconds": round(time.time() - started, 3),
        "guardrails_fired": guards.fired,
        "stopped_by": stopped_by,
    })

    # THE GATED ACTION IS A LOG ENTRY, NOT THE THING IT STANDS FOR: the
    # one write this agent performs is one structured record appended to
    # a local file (src/decision_log.py), never a real booking/letter/
    # email. Done here, once, at the single point every run reaches a
    # final decision - covering all three outcomes, not only `book`.
    record["log_confirmation"] = record_decision(record)
    return record


def _short(value, n=64):
    s = repr(value)
    return s if len(s) <= n else s[:n - 1] + "..."
