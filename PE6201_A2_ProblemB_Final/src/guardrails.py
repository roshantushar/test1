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

MAKE THE STOP LOUD. A cap that returns quietly is worse than the loop it
prevented - it converts a visible cost problem into an invisible
correctness problem. Every stop records why, in `fired`, which lands in
the decision record (see agent.py).
====================================================================
"""


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

    def _fire(self, kind, detail):
        self.fired.append({"guardrail": kind, "detail": detail})
