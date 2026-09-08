# D7 — Two Reproduced Failures

Both failures follow the method shown in the scaffold
(`A2_scaffold 2/demo_loop_failure.py`'s module docstring): **the working
agent, minus X**, not a separately written bad agent — and restoring X must
recover the original behaviour exactly. Both run on the scripted backend
only (no key, no network, no cost).

## Failure 1 — loop / control failure (layer: `guardrails.py`)

**X = action de-duplication.** Script: `src/demo_loop_failure.py` /
`experiments/d7_failures/failure_1_loop.py`. Evidence:
`results/d7/failure_1_loop.json`.

| | Before (guard in place) | Broken (guard deleted) | Restored (guard back) |
|---|---|---|---|
| Decision | `book` | `book` | `book` |
| Booked | OPH-C2, 2026-10-14, 11:20 | OPH-C2, 2026-10-14, 11:20 | OPH-C2, 2026-10-14, 11:20 |
| Turns | 5 | 7 | 5 |
| Tool calls | 6 | 10 | 6 |
| Tokens (estimate) | 29,460 | 48,080 | 29,460 |
| Cost (estimate) | US$0.004716 | US$0.007608 | US$0.004716 |
| Stopped by | — | — | — |

**Cost multiplier, broken over before: 1.63×.** Neither the step cap (7
turns, inside a cap of 8) nor the budget ceiling (48,080 tokens, inside a
ceiling of 60,000) fired — the run did not breach either bound, it simply
wasted a turn and 63% more tokens along the way. **No exception was raised.
The run reached the same correct answer as before.** A pass-rate table
alone would show this run as a clean pass; only the turn count and token
count, logged *while the run happened*, expose the fault — which is exactly
D7's stated lesson about instrumentation not being optional.

**Why the fix belongs in the code layer, not the other two.** A step cap or
budget ceiling only *bounds the damage* of a loop; neither *detects* one —
raise the repeat count in this same demo and both would eventually fire, but
later, and without ever naming the cause. A prompt fix ("please don't repeat
yourself") cannot be relied on either: the model is the thing that forgot,
so asking it more firmly not to forget is not a control, it's a hope. Only
the code layer — a de-duplication check evaluated over the actual sequence
of tool calls, independent of what the model believes it has or hasn't done
— can name the fault ("`check_referral_criteria` called again with identical
arguments") at the exact turn it happens.

**Restored matches before exactly** (`restored_matches_before: true` in the
saved evidence) — decision, booking, turns, tool calls, tokens and cost are
identical, confirming the deletion, not some other change, caused the
divergence.

## Failure 2 — tool interface failure (layer: `tools.py`, a different layer)

**X = `get_clinic_slots`' band safeguard** (the `band` filter, and the
requirement that it be supplied at all). Script:
`experiments/d7_failures/failure_2_slot_interface.py`. Evidence:
`results/d7/failure_2_slot_interface.json`.

| | Before (safeguard in place) | Broken (safeguard removed) | Restored |
|---|---|---|---|
| Decision | `book` | `book` | `book` |
| Booked | **OPH-C2, 2026-10-14, 11:20** (routine) | **OPH-C1, 2026-09-15, 09:40** (urgent) | OPH-C2, 2026-10-14, 11:20 |
| Turns | 5 | 6 | 5 |
| Tool calls | 6 | 7 | 6 |
| Tokens (estimate) | 29,460 | 38,220 | 29,460 |
| Cost (estimate) | US$0.004716 | US$0.006079 | US$0.004716 |
| `unsafe_booking` | — | **true** | — |

On `REF-5602` (a **routine** referral, 8-week window), the working interface
correctly finds and books the first routine-band slot with capacity
(2026-10-14). With the band filter removed, `get_clinic_slots` returns
*every* OPH slot inside the date window regardless of band — including two
genuinely **urgent**-band sessions (2026-09-15, 2026-09-22) reserved for
urgent patients. Because these dates are earlier, the earliest-by-date pick
grabs the urgent slot first.

**Why this produces an actual wrong booking, not just a wrong intermediate
answer that gets caught later.** This project's `book_slot` has its own
poka-yoke cross-check (see `docs/D2_TOOL_DESIGN.md`) that refuses to book
any `(clinic, date, time, specialty, band)` tuple that does not match a real
row. That check alone is *not* enough here: the broken run's calling code
takes `band` for the booking call from the **slot row's own label**
(`"urgent"`) rather than from `check_referral_criteria`'s assessed band
(`"routine"`) — a plausible thing for calling code to do once the tool
interface no longer forces band to come from the referral's assessed
urgency. Since a real urgent row genuinely exists at that clinic/date/time,
`book_slot`'s cross-check **passes**, and a routine patient is booked into a
slot reserved for an urgent case. **Two defences had to fail together**: the
interface safeguard, and the calling convention it was protecting.

**Why the fix belongs in the tool interface, not the other two layers.**
The step cap and budget ceiling bound *run length*; this run is short (6
turns, inside the cap of 8) and cheap, so neither would ever fire — they
cannot detect a wrong-but-confident answer reached quickly. Action
de-duplication does not apply either: nothing is repeated. Only the
interface itself — making `band` a **required, filtered** argument so a
wrong-band row can never be returned in the first place — closes this,
which is exactly the reasoning that made `band` required on
`get_clinic_slots` and made `specialty`+`band` required, cross-checked
arguments on `book_slot` in the working version (see
`docs/D2_TOOL_DESIGN.md`'s poka-yoke #1/#2).

**Restored matches before exactly** (`restored_matches_before: true`).

## The measures, side by side (both failures)

| Measure | Failure 1 (loop) | Failure 2 (interface) |
|---|---|---|
| Turns, before → broken | 5 → 7 | 5 → 6 |
| Calls, before → broken | 6 → 10 | 6 → 7 |
| Tokens (est.), before → broken | 29,460 → 48,080 | 29,460 → 38,220 |
| Cost (est.), before → broken | US$0.004716 → US$0.007608 | US$0.004716 → US$0.006079 |
| Pass/fail (code check) | pass (same correct answer) | **fail** (wrong booking) |
| Stop reason | none (neither cap fired) | none (neither cap fired) |
| Guard that would have caught it | action de-duplication (deleted) | `get_clinic_slots`' band filter (deleted) |
| Unsafe booking | **No** — wastes cost, reaches the right answer | **Yes** — books a routine patient into an urgent-reserved slot |

The two failures are deliberately at different layers and have different
consequences: Failure 1 is a **cost/efficiency** fault that happens to still
land on the correct decision; Failure 2 is a **correctness/safety** fault
that produces a genuinely wrong, irreversible booking. Both are invisible to
the step cap and the budget ceiling, and both are only visible because this
project's instrumentation records turns, calls, tokens and cost on every run
— the shared lesson D7 is built to demonstrate.
