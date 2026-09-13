"""
PE6201 A2 Problem B (Final) - THE TWO BACKENDS  (D5)
====================================================================
A backend answers ONE question: given the transcript so far, what does
the agent do next? It returns either

    {"thought": "...", "calls": [(name, args), ...]}   -> call tool(s)
    {"thought": "...", "final": {...}}                  -> conclude

EXACTLY ONE FUNCTION KNOWS A VENDOR EXISTS: `_live_call`, reused idea
from the scaffold (A2_scaffold 2/backends.py).

--------------------------------------------------------------------
WHY THIS BACKEND IS NOT A LIST OF HAND-WRITTEN TRANSCRIPTS

The scaffold scripts each case as a literal, hand-typed sequence of
moves (SCRIPTS["REF-5602"] = [...]). That does not scale to 30-50 cases,
and worse: for every NEW case a team writes, the "script" is really just
a restatement of what the team already believes the answer key says -
which risks the scripted backend quietly encoding the label instead of
reasoning to it.

Instead, ScriptedPolicyBackend is a small, deterministic, RULE-FOLLOWING
policy, implemented once, that decides its own next move by calling the
SAME tool layer (tools.py) the live model would call, and applying the
SAME fixed order of checks documented in prompt.RULES:

    injection -> red flag -> wrong department -> missing test ->
    duplicate appointment -> compute window -> query slots -> book

It never opens expected_outcomes_B.json (nothing in this file does -
only harness.py may, per the ground-truth firewall) and it never
hand-codes "REF-5602 books OPH-C2 on 2026-10-14" anywhere. That fact
is a CONSEQUENCE of walking the real data through the real tools, not
an input, which is what makes 30-50 scripted cases tractable and honest
at the same time. It is deliberately simple (a straight-line decision
tree, no retries, no exploration) - it exists to test the CODE (tools,
guardrails, harness), the same purpose the scaffold's SCRIPTS served.

`parallel=False` reproduces the same decisions one call per turn, for
the D2(c) sequential-vs-parallel comparison.
====================================================================
"""
import datetime
import http.client
import json
import time
import urllib.error
import urllib.request

import test1.src.config as config
import test1.src.tools as tools


class ScriptedPolicyBackend:
    """Deterministic, offline, free. See module docstring."""

    name = "scripted"

    def __init__(self, case_id, parallel=True, force_moves=None):
        self.case_id = case_id
        self.parallel = parallel
        # `force_moves`: an explicit list of moves to replay instead of
        # deriving them - used ONLY by the D7 loop-failure demo, to
        # inject a repeated call into an otherwise-real transcript.
        self._forced = force_moves
        self._moves = self._forced if self._forced is not None else self._derive_moves()
        self._i = 0

    # -----------------------------------------------------------------
    def next_move(self, transcript):
        if self._i >= len(self._moves):
            return {"thought": "policy exhausted without a conclusion",
                    "final": {"decision": "escalate",
                              "reason": "policy ended without a conclusion",
                              "trigger": "policy_exhausted"}}
        move = self._moves[self._i]
        self._i += 1
        return move

    @staticmethod
    def token_estimate(transcript):
        # ESTIMATES ONLY - not a measurement. D6 uses these labelled as
        # such; the live battery is what supplies MEASURED counts.
        return 1500 + 550 * len(transcript), 110

    # -----------------------------------------------------------------
    def _derive_moves(self):
        """Walk the real tool layer, in the fixed protocol order, and
        build the move list a correct agent would produce. Never touches
        the answer key."""
        cid = self.case_id
        moves = []

        # turn 1: get_referral, alone - nothing else can be known yet.
        ref = tools.get_referral(cid)
        moves.append({"thought": "Fetch the referral. Nothing else can "
                                  "be known before this returns.",
                      "calls": [("get_referral", {"referral_id": cid})]})
        if ref is None:
            moves.append({"thought": "No such referral - a broken case.",
                          "final": {"decision": "escalate",
                                    "reason": "referral id does not resolve",
                                    "trigger": "broken_case"}})
            return moves

        specialty = ref["specialty"]
        patient_id = ref["patient_id"]

        # turn 2: check_referral_criteria + lookup_patient - independent
        # of each other, both depend only on turn 1's output.
        crit_call = ("check_referral_criteria",
                     {"specialty": specialty, "referral_id": cid})
        pat_call = ("lookup_patient", {"patient_id": patient_id})
        calls2 = [crit_call, pat_call] if self.parallel else [crit_call]
        moves.append({"thought": "Two independent questions: the "
                                  "department's protocol, and whether "
                                  "this patient already has an "
                                  "appointment. %s"
                                  % ("Fire both together." if self.parallel
                                     else "Ask the criteria first."),
                      "calls": calls2})
        crit = tools.check_referral_criteria(specialty, cid)
        if not self.parallel:
            moves.append({"thought": "Now the independent second "
                                      "question, in its own turn.",
                          "calls": [pat_call]})
        patient = tools.lookup_patient(patient_id)

        if crit is None or patient is None:
            moves.append({"thought": "A lookup failed - a broken case.",
                          "final": {"decision": "escalate",
                                    "reason": "specialty or patient does not resolve",
                                    "trigger": "broken_case"}})
            return moves

        # ---- the fixed order of gates, exactly as prompt.RULES states --
        if crit["injection_detected"]:
            moves.append({"thought": "The free text contains an "
                                      "instruction aimed at the system. "
                                      "It is not followed. Escalate.",
                          "final": {"decision": "escalate",
                                    "trigger": "instruction_in_referral_free_text",
                                    "reason": "Free text contained: %r. Not "
                                              "followed. No slot queried, "
                                              "nothing booked."
                                              % crit["injection_span"]}})
            return moves

        if crit["red_flag_term"]:
            moves.append({"thought": "Red flag present. Escalate to the "
                                      "triage nurse; do not query a slot.",
                          "final": {"decision": "escalate",
                                    "trigger": "red_flag_term",
                                    "reason": "Red-flag term %r matched under "
                                              "specialty %s. escalate_to "
                                              "triage nurse."
                                              % (crit["red_flag_term"], specialty)}})
            return moves

        if not crit["right_department"]:
            moves.append({"thought": "The summary does not describe a "
                                      "%s problem. Wrong department - "
                                      "escalate, do not re-route."
                                      % specialty,
                          "final": {"decision": "escalate",
                                    "trigger": "specialty_mismatch",
                                    "reason": "Referral requested %s but the "
                                              "clinical summary does not "
                                              "match that department. "
                                              "escalate_to triage nurse."
                                              % specialty}})
            return moves

        if crit["missing_tests"]:
            missing = crit["missing_tests"][0]
            moves.append({"thought": "A mandatory test is not attached. "
                                      "Name it exactly and stop - no slot "
                                      "query for an incomplete referral.",
                          "final": {"decision": "request_information",
                                    "missing": "%s %s" % (missing["name"], missing["code"]),
                                    "reason": "%s (%s) is mandatory for %s and "
                                              "is not attached."
                                              % (missing["name"], missing["code"], specialty)}})
            return moves

        dup = _find_duplicate(patient, specialty)
        if dup:
            moves.append({"thought": "A future appointment already exists "
                                      "in this specialty. Escalate; do not "
                                      "book a second one.",
                          "final": {"decision": "escalate",
                                    "trigger": "duplicate_future_appointment",
                                    "reason": "Patient already has a future "
                                              "%s appointment at %s on %s."
                                              % (specialty, dup["clinic"], dup["date"])}})
            return moves

        # ---- all gates passed: compute the window, then search slots ---
        band, weeks = crit["band"], crit["window_weeks"]
        win_call = ("compute_window", {"window_weeks": weeks})
        moves.append({"thought": "All checks passed. Compute the legal "
                                  "window for band %r before searching." % band,
                      "calls": [win_call]})
        window = tools.compute_window(weeks)

        slot_call = ("get_clinic_slots",
                     {"specialty": specialty, "band": band,
                      "from": window["from"], "to": window["to"]})
        moves.append({"thought": "Search for a free slot inside the "
                                  "window, in the correct band.",
                      "calls": [slot_call]})
        slots = sorted(tools.get_clinic_slots(specialty, band, **window),
                       key=lambda s: (s["date"], s["time"]))

        if not slots:
            moves.append({"thought": "No slot with capacity exists inside "
                                      "the window. Escalate - do not widen "
                                      "the window or drop the band.",
                          "final": {"decision": "escalate",
                                    "trigger": "no_slot_in_window",
                                    "reason": "Band %s, window %s to %s. No "
                                              "%s slot with capacity in that "
                                              "window."
                                              % (band, window["from"], window["to"], specialty)}})
            return moves

        chosen = slots[0]
        book_call = ("book_slot",
                     {"clinic": chosen["clinic"], "date": chosen["date"],
                      "time": chosen["time"], "referral_id": cid,
                      "specialty": specialty, "band": band})
        moves.append({"thought": "Book the first available slot inside "
                                  "the window. Irreversible - goes through "
                                  "the gate.",
                      "calls": [book_call]})
        result = tools.book_slot(**book_call[1])

        if not result.get("booked"):
            moves.append({"thought": "The slot did not actually book - "
                                      "escalate rather than guess again.",
                          "final": {"decision": "escalate",
                                    "trigger": "booking_failed",
                                    "reason": result.get("error", "booking failed")}})
            return moves

        weeks_out = (datetime.date.fromisoformat(chosen["date"])
                     - datetime.date.fromisoformat(tools.as_of())).days // 7
        moves.append({"thought": "Booked. Record band, window, tests and "
                                  "the duplicate check.",
                      "final": {"decision": "book",
                                "booked": {"clinic": chosen["clinic"],
                                           "date": chosen["date"],
                                           "time": chosen["time"]},
                                "reason": "Band %s, window %s to %s, booked "
                                          "at %d week(s). All mandatory "
                                          "tests present. No duplicate "
                                          "appointment for this patient in "
                                          "%s."
                                          % (band, window["from"], window["to"],
                                             weeks_out, specialty)}})
        return moves


def _find_duplicate(patient_lookup, specialty):
    """A duplicate is a FUTURE appointment in the SAME specialty. Uses
    as_of() as the clock, exactly as tools.lookup_patient documents."""
    today = tools.as_of()
    for appt in patient_lookup["patient"].get("existing_appointments", []):
        if appt["specialty"] == specialty and appt["date"] > today:
            return appt
    return None


def make_scripted(case_id, parallel=True, force_moves=None):
    return ScriptedPolicyBackend(case_id, parallel=parallel, force_moves=force_moves)


# =====================================================================
# LIVE
# =====================================================================
class LiveBackend:
    """Real model via OpenRouter. Costs money. Used only by D2(b)'s live
    comparison and D5(b)'s battery - both unrun in this environment, see
    STATUS.md. Captures ACTUAL usage from the API response, fixing the
    scaffold's deliberate zero-tokens placeholder."""

    name = "live"

    def __init__(self, case_id, system_prompt):
        self.case_id = case_id
        self.system_prompt = system_prompt
        self.last_usage = (0, 0)

    def next_move(self, transcript):
        messages = [{"role": "system", "content": self.system_prompt}]
        for entry in transcript:
            messages.append({"role": entry["role"], "content": entry["content"]})
        raw, usage = _live_call(messages)
        self.last_usage = usage
        return _parse_move(raw)

    def token_estimate(self, transcript):
        # Real usage from the last call, not an estimate.
        return self.last_usage


def _parse_move(text):
    """Parse the model's reply as JSON. Tries the raw text first, then two
    tolerant fallbacks for common (non-compliant, but recoverable) live
    formatting - a markdown code fence around the JSON, or extra prose
    around a single JSON object - before giving up and recording the
    failure loudly rather than guessing at intent."""
    candidates = [text, _strip_code_fence(text)]
    brace = _extract_braced(text)
    if brace:
        candidates.append(brace)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        # Valid JSON that is not a top-level object (e.g. a bare list) is
        # syntactically parseable but matches neither documented move
        # shape - every downstream call assumes move.get(...), so treat
        # this the same as unparseable rather than crashing on the first
        # .get() (observed live: a model returned a top-level JSON array).
        if isinstance(parsed, dict):
            return parsed
    return {"thought": "unparseable: %s" % text[:200],
            "final": {"decision": "escalate",
                      "reason": "model did not return parseable JSON",
                      "trigger": "unparseable_output"}}


def _strip_code_fence(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[: -3]
        return t.strip()
    return t


def _extract_braced(text):
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return None


def _live_call(messages):
    """>>> THE ONLY FUNCTION IN THIS PROJECT THAT KNOWS A VENDOR <<<"""
    if not config.API_KEY:
        raise SystemExit(
            "\n  BACKEND is 'live' but OPENROUTER_API_KEY is not set.\n"
            "    export OPENROUTER_API_KEY='sk-or-...'\n"
            "  Or set BACKEND = 'scripted' in config.py, which is free.\n")
    def _post(use_json_mode):
        fields = {"model": config.MODEL, "messages": messages, "temperature": 0}
        if use_json_mode:
            fields["response_format"] = {"type": "json_object"}
        body = json.dumps(fields).encode()
        req = urllib.request.Request(
            config.BASE_URL.rstrip("/") + "/chat/completions", data=body,
            headers={"Authorization": "Bearer " + config.API_KEY,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.load(r)
        if "choices" not in payload:
            # A 200 response with no "choices" key is the provider's own
            # transient-error shape (e.g. {"error": {...}} for an
            # upstream rate-limit or overload) - observed against
            # mistralai/mistral-nemo via the DeepInfra route mid-battery,
            # with no HTTPError raised since the HTTP status was 200.
            # Surface it the same way as a network-level failure so the
            # retry wrapper below can retry it instead of crashing.
            raise RuntimeError("provider returned no 'choices': %r" % (payload,))
        return payload

    def _post_with_retries(use_json_mode, attempts=3):
        # A live HTTP call can fail transiently - a truncated chunked
        # response (http.client.IncompleteRead, observed against this
        # OpenRouter endpoint mid-battery), a dropped connection, a read
        # timeout, or a 200 response carrying a provider-side error
        # instead of a completion - none of which reflect anything about
        # the model's own behaviour. Retry a few times with a short
        # backoff before giving up, rather than letting one flaky
        # network or provider blip crash an entire multi-hour live
        # evaluation run.
        last_exc = None
        for attempt in range(attempts):
            try:
                return _post(use_json_mode)
            except (http.client.IncompleteRead, ConnectionError, TimeoutError, RuntimeError) as e:
                last_exc = e
                if attempt < attempts - 1:
                    time.sleep(2 * (attempt + 1))
        raise last_exc

    # Not every model on OpenRouter accepts response_format=json_object.
    # Ask for it (it materially improves JSON compliance on models that
    # support it); on a 4xx from the provider, retry once without it
    # rather than failing the whole run over a formatting hint.
    #
    # OpenRouter routes a single model id across MULTIPLE upstream
    # providers (e.g. qwen/qwen-2.5-72b-instruct was observed served by
    # both DeepInfra and Novita within the same battery run) and picks
    # between them per-request based on availability - so a 400 here can
    # mean "the provider THIS request happened to land on doesn't
    # support json_object" or "that provider is rate-limited", not "this
    # model can never work". A routing retry can land on a different,
    # working provider. A 5xx (observed: 504 Gateway Timeout on
    # meta-llama/llama-3.1-8b-instruct) is likewise a transient gateway/
    # server condition, not a reason to believe the model itself is
    # broken - so BOTH 4xx and 5xx are retried through the same outer
    # loop, rather than failing the whole run over one unlucky routing
    # decision or one slow gateway. A provider's inline error (a 200
    # response with no "choices" - _post's own RuntimeError, e.g.
    # "response format json_object is not supported" from a provider
    # that landed a plain 400-shaped error inside a 200 envelope,
    # observed on qwen/qwen-2.5-72b-instruct) is the SAME routing
    # problem wearing a different shape, and needs the same outer retry
    # - catching only HTTPError here left it exhausting all of
    # _post_with_retries' own attempts and then crashing the whole
    # battery on the very next routing hiccup.
    last_route_exc = None
    for route_attempt in range(3):
        try:
            payload = _post_with_retries(use_json_mode=True)
            break
        except (urllib.error.HTTPError, RuntimeError) as e:
            try:
                payload = _post_with_retries(use_json_mode=False)
                break
            except (urllib.error.HTTPError, RuntimeError) as e2:
                last_route_exc = e2
                if route_attempt < 2:
                    time.sleep(3 * (route_attempt + 1))
    else:
        raise last_route_exc

    content = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    return content, (usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


def make_backend(case_id, system_prompt="", parallel=True, force_moves=None):
    if config.BACKEND == "scripted":
        return make_scripted(case_id, parallel=parallel, force_moves=force_moves)
    if config.BACKEND == "live":
        return LiveBackend(case_id, system_prompt)
    raise SystemExit("BACKEND must be 'scripted' or 'live', not %r" % config.BACKEND)
