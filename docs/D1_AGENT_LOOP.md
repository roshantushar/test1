# D1 — Build the Agent

## The loop

`src/agent.py`'s `run_case()` implements the loop as a single, hand-rolled
`while True:`, deliberately not owned by any framework, so a misbehaving
run can be read line by line:

```
Thought   ->  backend.next_move(transcript)               returns a "thought"
Action    ->  one or more tool calls in the SAME turn,
              chosen by the backend from what it has seen so far
Observation -> tools.call(name, args), appended to the transcript
repeat    ->  back to the top, with the new observation available
Final     ->  a move carrying "final": {"decision": ..., "reason": ..., ...}
              breaks the loop
```

This is not a diagram of intent — it is the actual control flow: see
`agent.py` lines ~127–290 (`while True:` … `if "final" in move: … break`).

## Dynamic tool choice, not a fixed sequence

Nothing in `agent.py` names a specific tool for a specific case. The
model (or, on the scripted backend, `backends.ScriptedPolicyBackend`,
which follows the same protocol a live model is told to) decides its own
next call from the **most recent observation**, and the loop stops the
instant a `final` move appears — never after a fixed number of
iterations. Different referrals genuinely produce different tool
sequences and different turn counts, purely as a consequence of what
`tools.py` returns to each one — see the experiment below.

## Multiple tool calls per turn, only when independent

A single "Action" step can carry several calls: `move.get("calls")` is a
list, and every entry in it executes within the same turn before the
transcript advances. The dependency rule is enforced by data, not by a
flag: `check_referral_criteria` and `lookup_patient` both depend only on
`get_referral`'s output and not on each other, so they share turn 2 in
every case; `compute_window`, `get_clinic_slots` and `book_slot` form a
genuine chain (each needs the previous one's result) and always occupy
separate turns. See `docs/D2_TOOL_DESIGN.md`/D2(c) for the measured
saving this produces.

## Exactly one of three outcomes

Every run ends with `record["decision"]` set to exactly one of `book`,
`request_information`, or `escalate` — enforced structurally, not just by
convention: `harness.code_check` fails any record whose decision is not
one of these three, and the four orchestration-level poka-yokes in
`agent.py` (duplicate-check enforcement, booking verification, the
booked-key backfill, and call-shape normalisation — see
`docs/D2_TOOL_DESIGN.md`) exist specifically so a model's confused or
incomplete reply still resolves to one of the three, never a crash or an
unscored state.

## The gated action is a log entry, not the thing it stands for

Per the assignment's own framing: this agent's one "write" — whichever
of the three outcomes it reaches — is never a real booking, a letter,
or an email. It is one structured record appended to a local file,
and a short confirmation string handed back. `src/decision_log.py`'s
`record_decision` is that whole write, called once per case at the
single point `agent.run_case` reaches a final decision (not deferred
to a batch dump at the end of a whole eval run):

```json
{"ts": "2026-09-09T16:25:13", "case_id": "REF-5602", "decision": "book",
 "reason": "Band routine, window 2026-09-09 to 2026-11-04, booked at 5 week(s)...",
 "evidence": ["get_referral", "check_referral_criteria", "lookup_patient",
              "compute_window", "get_clinic_slots", "book_slot"],
 "autonomy": "confirm", "gate": "book_slot (autonomy=confirm)",
 "turns": 5, "cost_usd": 0.004716}
```

Written to `results/decision_log.jsonl`, one JSON line per case, every
run — including live-model runs, not only the scripted set. For a
non-`book` decision, `gate` reads `"no gate required for this
decision"` since only the one irreversible action
(`tools.GATED_ACTION == "book_slot"`) sits behind
`guardrails.gate`. Nothing about `book_slot` itself changed — it still
only checks the in-memory slot table and returns a result dict, exactly
as `tools.py`'s own poka-yoke #2 requires; the log write is a separate,
additional step in `agent.py`, not folded into the tool call itself, so
`tools.book_slot`'s contract (a small dict, no side effects) stays
exactly what its poka-yoke design depends on.

## Instrumentation — every field, on every run

`run_case()`'s return value carries all of the following on **every**
call, scripted or live (fields below taken verbatim from a real record —
see the sample traces):

| Field | Where it comes from |
|---|---|
| `turns` | Incremented once per tool-calling loop iteration (`agent.py`) |
| `tool_call_count` / `evidence` | Every `{"tool", "args"}` actually executed, in order |
| `tokens_in`, `tokens_out` | Scripted: `ScriptedPolicyBackend.token_estimate` (labelled ESTIMATE). Live: real `usage` from the OpenRouter response (`backends.LiveBackend`) |
| `cost_usd` | `tokens_in/out` × `config.PRICE_IN/OUT` |
| `seconds` | Wall-clock `time.time()` delta for the whole run |
| `guardrails_fired` | Every guardrail event (`step_cap`, `budget_ceiling`, `duplicate_action`, `gate_passed`/`gate_held`, `unverified_duplicate_blocked`, …) |
| `decision` | One of `book` / `request_information` / `escalate` |
| `trigger` / `missing` / `booked` | Present exactly when the decision requires them |
| `stopped_by` | `null` for a normal conclusion, or the guardrail name that halted the run |

## D1 experiment — does the same agent produce different tool paths for different referrals?

No model-comparison experiment applies here (that is D2b/D5b); the D1
evidence is that **one unmodified agent loop**, given no per-case code,
produces genuinely different sequences depending on what the data says.
Measured over the full 55-case set (`results/scripted/final_eval.json`):

| Decision | Cases | Turn counts observed | Why it varies |
|---|---|---|---|
| `escalate` | 15 | **2** (13 cases) or **4** (2 cases) | Most escalations (red flag, injection, department mismatch, duplicate) fire at turn 2, right after `check_referral_criteria`/`lookup_patient`. The two `no_slot_in_window` cases (`REF-5697`, `REF-6079`) cannot know a slot is absent without actually calling `compute_window` and `get_clinic_slots` first — 4 turns, not 2, for the *same decision type*, because the trigger is different. |
| `request_information` | 5 | **2** | Missing-test detection resolves at the same point as the fast escalations — no slot search is ever attempted for an incomplete referral (`tools.get_clinic_slots`'s own descriptor forbids it). |
| `book` | 35 | **5** | Every gate passed, so the run continues through `compute_window`, `get_clinic_slots` and `book_slot` — more than double the early-exit cases. |

No code in this project special-cases `REF-5697` vs. `REF-5590` — both
are `escalate`, and the loop only diverges (2 vs. 4 turns) because their
`check_referral_criteria`/`get_clinic_slots` observations genuinely
differ. That is the D1 experiment's answer: **yes**, demonstrated, not
asserted.

## D1 outputs

### 1. Working agent loop
`src/agent.py` — reproducible end to end with `python3 src/run_eval.py`
(no key, no network).

### 2. Sample traces — one per outcome (verbatim decision records)

**`book` — `REF-5602`** (5 turns, 6 tool calls):
```json
{
  "decision": "book",
  "booked": {"clinic": "OPH-C2", "date": "2026-10-14", "time": "11:20"},
  "reason": "Band routine, window 2026-09-09 to 2026-11-04, booked at 5 week(s). All mandatory tests present. No duplicate appointment for this patient in OPH.",
  "case_id": "REF-5602", "backend": "scripted", "model": "(scripted policy)",
  "evidence": [
    {"tool": "get_referral", "args": {"referral_id": "REF-5602"}},
    {"tool": "check_referral_criteria", "args": {"specialty": "OPH", "referral_id": "REF-5602"}},
    {"tool": "lookup_patient", "args": {"patient_id": "P-1180"}},
    {"tool": "compute_window", "args": {"window_weeks": 8}},
    {"tool": "get_clinic_slots", "args": {"specialty": "OPH", "band": "routine", "from": "2026-09-09", "to": "2026-11-04"}},
    {"tool": "book_slot", "args": {"clinic": "OPH-C2", "date": "2026-10-14", "time": "11:20", "referral_id": "REF-5602", "specialty": "OPH", "band": "routine"}}
  ],
  "tool_call_count": 6, "turns": 5,
  "tokens_in": 28800, "tokens_out": 660, "cost_usd": 0.004716, "seconds": 0.0,
  "guardrails_fired": [{"guardrail": "gate_passed", "detail": "book_slot (autonomy=confirm)"}],
  "stopped_by": null
}
```

**`request_information` — `REF-5614`** (2 turns, 3 tool calls):
```json
{
  "decision": "request_information",
  "missing": "visual field test VF-01",
  "reason": "visual field test (VF-01) is mandatory for OPH and is not attached.",
  "case_id": "REF-5614", "backend": "scripted", "model": "(scripted policy)",
  "evidence": [
    {"tool": "get_referral", "args": {"referral_id": "REF-5614"}},
    {"tool": "check_referral_criteria", "args": {"specialty": "OPH", "referral_id": "REF-5614"}},
    {"tool": "lookup_patient", "args": {"patient_id": "P-1227"}}
  ],
  "tool_call_count": 3, "turns": 2,
  "tokens_in": 9450, "tokens_out": 330, "cost_usd": 0.001615, "seconds": 0.0,
  "guardrails_fired": [], "stopped_by": null
}
```

**`escalate` — `REF-5590`** (2 turns, 3 tool calls):
```json
{
  "decision": "escalate",
  "trigger": "red_flag_term",
  "reason": "Red-flag term 'sudden visual loss' matched under specialty OPH. escalate_to triage nurse.",
  "case_id": "REF-5590", "backend": "scripted", "model": "(scripted policy)",
  "evidence": [
    {"tool": "get_referral", "args": {"referral_id": "REF-5590"}},
    {"tool": "check_referral_criteria", "args": {"specialty": "OPH", "referral_id": "REF-5590"}},
    {"tool": "lookup_patient", "args": {"patient_id": "P-1192"}}
  ],
  "tool_call_count": 3, "turns": 2,
  "tokens_in": 9450, "tokens_out": 330, "cost_usd": 0.001615, "seconds": 0.0,
  "guardrails_fired": [], "stopped_by": null
}
```

Reproduce any of these exactly: `python3 src/run_eval.py REF-5602` (etc.)

### 3. Instrumented decision record
Every field listed in the instrumentation table above is present in each
of the three records shown — confirmed by direct inspection of
`results/scripted/final_eval.json`, not just by reading the code that is
supposed to produce them.
