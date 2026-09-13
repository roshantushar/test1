"""
PE6201 A2 Problem B (Final) - GUARDRAIL LAYER  (D3a)
====================================================================
Own implementation, following the shape shown in the scaffold
(A2_scaffold 2/guardrails.py): four checks, none of which involve a
model, so they can be tested deterministically on the scripted backend.

    1. STEP CAP              stop after N turns
    2. BUDGET CEILING        stop after N tokens
    3. ACTION DE-DUPLICATION stop repeating an identical call
    4. AUTONOMY GATE         hold book_slot for a human, per AUTONOMY
    5. UNVERIFIED-DUPLICATE  refuse book_slot if a real duplicate
                             appointment exists and was never (or was
                             wrongly) cleared - see agent.py, which
                             enforces the lookup_patient check itself
                             immediately before book_slot rather than
                             trusting the model to have done it.
    6. SINGLE-BOOKING        refuse a SECOND book_slot success in the
                             same run, even with completely different
                             (valid) arguments - action de-duplication
                             (#3) only catches an IDENTICAL repeat, so a
                             model that books one slot and then books a
                             DIFFERENT one too (e.g. after a confused
                             retry) would otherwise double-book the
                             patient with neither guard noticing.
    7. MONTHLY LIMIT         refuse a new run for a CALLER (referring
                             clinic - the natural caller identity for
                             Problem B) once it has already made
                             config.MAX_MONTHLY_REQUESTS_PER_CALLER
                             requests this period. Unlike 1-6, this is
                             cross-run state (usage accumulated OVER
                             TIME, not within one run) - see the
                             module-level counter below, deliberately
                             separate from the per-run Guardrails
                             instance every other check lives on.

MAKE THE STOP LOUD. A cap that returns quietly is worse than the loop it
prevented - it converts a visible cost problem into an invisible
correctness problem. Every stop records why, in `fired`, which lands in
the decision record (see agent.py).
====================================================================
"""


# Cross-run state for guardrail #7 (monthly limit per caller) -
# deliberately a MODULE-level dict, not an attribute of any one
# Guardrails instance: usage accumulates ACROSS runs over a real
# calendar period, unlike every other guardrail here, which is
# per-run state that starts clean each time (D4's isolation
# requirement - see the Guardrails class docstring below). A real
# deployment would back this with a database keyed by caller and
# billing period; this in-memory dict is the same idea at demo scale,
# and reset_monthly_counts() exists so D3(b)'s test suite (and any
# other caller) can guarantee a clean starting count.
_monthly_request_counts = {}


def reset_monthly_counts():
    """Clears guardrail #7's cross-run counters. Call this between
    guardrail-checklist cases (or at the start of a new billing period
    in a real deployment) - never mid-run."""
    _monthly_request_counts.clear()


class GuardrailStop(Exception):
    """Raised when the code layer halts a run. Carries the reason so the
    decision record can say what stopped it."""

    def __init__(self, reason, detail=""):
        self.reason = reason
        self.detail = detail
        super().__init__("%s: %s" % (reason, detail) if detail else reason)


class Guardrails:
    """One instance per run (see agent.run_case). Never shared between
    cases - D4 requires every case to start clean."""

    def __init__(self, max_turns, max_tokens, autonomy):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.autonomy = autonomy
        self.seen_actions = set()
        self.fired = []

    # ---- 1 - step cap -------------------------------------------------
    def check_turns(self, turn):
        if turn > self.max_turns:
            self._fire("step_cap", "reached %d turns" % self.max_turns)
            raise GuardrailStop(
                "step_cap", "hit the %d-turn cap without a conclusion" % self.max_turns)

    # ---- 2 - budget ceiling --------------------------------------------
    def check_budget(self, tokens_so_far):
        if tokens_so_far > self.max_tokens:
            self._fire("budget_ceiling", "%d tokens" % tokens_so_far)
            raise GuardrailStop(
                "budget_ceiling", "spent %d tokens, ceiling is %d"
                                  % (tokens_so_far, self.max_tokens))

    # ---- 3 - action de-duplication -------------------------------------
    def check_duplicate(self, tool, args):
        """A loop has no memory of its own actions unless given one. This
        IS that memory - see experiments/d7_failures/failure_1_loop.py for
        what happens with this check deleted."""
        signature = (tool, repr(sorted(args.items())))
        if signature in self.seen_actions:
            self._fire("duplicate_action", "%s repeated" % tool)
            raise GuardrailStop(
                "duplicate_action",
                "%s called again with identical arguments - the loop is "
                "not progressing" % tool)
        self.seen_actions.add(signature)

    # ---- 4 - autonomy gate ----------------------------------------------
    def gate(self, action_name, payload, approve=None):
        """Called ONLY immediately before the irreversible action
        (tools.GATED_ACTION == "book_slot"). Gating the agent as a whole
        instead would not be an agent, it would be a form - see
        docs/D0_AGENT_JUSTIFICATION.md.
        """
        if self.autonomy == "act":
            self._fire("gate_passed", "%s (autonomy=act)" % action_name)
            return True
        if self.autonomy == "suggest":
            self._fire("gate_held", "%s (autonomy=suggest)" % action_name)
            return False
        ok = bool(approve and approve(action_name, payload))
        self._fire("gate_%s" % ("passed" if ok else "held"),
                   "%s (autonomy=confirm)" % action_name)
        return ok

    # ---- 5 - unverified-duplicate (book_slot precondition) --------------
    def check_no_unverified_duplicate(self, duplicate, specialty):
        """Called by agent.py immediately before book_slot, with the
        result of a duplicate-appointment check the AGENT ITSELF just
        performed (auto-injecting lookup_patient if the model had not
        already called it). If a genuine future appointment in the same
        specialty exists, the booking is refused outright - regardless
        of what the model's own reasoning concluded. This closes a gap a
        prompt instruction alone could not: see STATUS.md, where
        openai/gpt-4o-mini skipped this exact check on every live
        booking trial."""
        if duplicate:
            self._fire("unverified_duplicate_blocked",
                       "a future %s appointment already exists (%s on %s)"
                       % (specialty, duplicate.get("clinic"), duplicate.get("date")))
            raise GuardrailStop(
                "unverified_duplicate",
                "refused to book: patient already has a future %s "
                "appointment at %s on %s"
                % (specialty, duplicate.get("clinic"), duplicate.get("date")))

    # ---- 6 - single booking per run --------------------------------------
    def check_single_booking(self, already_booked_once):
        """Called by agent.py before EVERY book_slot attempt (tool call or
        merely-declared). A SECOND successful booking in the same run is
        refused outright, regardless of whether its arguments differ from
        the first - the irreversible action may happen at most once per
        referral, full stop. This is deliberately independent of action
        de-duplication (#3), which only catches an identical repeat and
        would let two DIFFERENT bookings both through."""
        if already_booked_once:
            self._fire("single_booking_blocked",
                       "book_slot already succeeded once this run - refusing a second booking")
            raise GuardrailStop(
                "duplicate_booking_attempt",
                "book_slot already succeeded once this run - a referral "
                "may be booked at most once")

    # ---- 7 - monthly limit per caller ------------------------------------
    def check_monthly_limit(self, caller_id, limit):
        """Called by agent.py once per run, as early as possible (right
        after get_referral resolves the caller's identity, before any
        further tool calls) - refuses to proceed if this caller has
        already reached `limit` requests this period. Increments the
        module-level counter as part of the check, so the count reflects
        RUNS ATTEMPTED, not runs that completed successfully - a caller
        cannot dodge the cap by having its requests fail partway
        through."""
        _monthly_request_counts[caller_id] = _monthly_request_counts.get(caller_id, 0) + 1
        count = _monthly_request_counts[caller_id]
        if count > limit:
            self._fire("monthly_limit_exceeded",
                       "%s: %d requests this period, limit is %d"
                       % (caller_id, count, limit))
            raise GuardrailStop(
                "monthly_limit_exceeded",
                "%s has reached %d requests this period (limit %d) - "
                "refusing further runs until the period resets"
                % (caller_id, count, limit))

    def _fire(self, kind, detail):
        self.fired.append({"guardrail": kind, "detail": detail})
