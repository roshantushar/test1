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

### The four things the assignment requires this failure to report

**1 — the instrumentation that found it.** Every field in the table
above (`turns`, `tool_calls`, `tokens_total`, `cost_usd`, `stopped_by`,
`guardrails_fired`) is recorded by `agent.run_case` on every single
run, live or scripted, per D1's instrumentation requirement — not
added retroactively for this failure. Without turns-and-cost logged
per run, this failure is invisible: the decision, the booking, and the
absence of any exception are all identical before and after, so a
system that only checked "did it reach the right answer" would report
this run as a clean pass.

**2 — the turn distribution across the whole evaluation set, not one
number** (`results/scripted/final_eval.json`, 55 cases/95 trials):

| | Value |
|---|---|
| Median turns | 2 |
| Mean turns | 3.232 |
| Worst-case turns | 5 |
| Minimum turns | 2 |
| Trials hitting the step cap | 0 / 95 |
| Step cap in force | 8 |

This distribution is exactly the evidence `MAX_TURNS=8` was set from
(`docs/D3_GUARDRAILS.md`'s "why the step cap is 8"): a median of 2 and
a worst legitimate case of 5 leaves 3 turns of headroom above the
worst real run — enough to absorb one wasted turn like this failure's
7, without masking a genuine runaway (which is exactly why THIS
failure's 7 turns never tripped the cap: it is still short of a real
loop, which is the whole point being demonstrated).

**3 — the fix, and why the other TWO code-layer options would not have
caught it, and why the tool interface and prompt layers would not
either.** Only action de-duplication actually catches this failure;
none of this project's other five guardrails do:
- **Step cap / budget ceiling** only *bound the damage* of a loop, they
  do not *detect* one — raise the repeat count in this same demo and
  both would eventually fire, but later, and without ever naming the
  cause (`stopped_by` would read `step_cap`, not `duplicate_action`).
- **The tool interface** (the layer Failure 2 below lives in) cannot
  fix this either: `check_referral_criteria` and `lookup_patient`
  behaved correctly and returned correct data both times they were
  called — nothing about their signature or return shape was wrong.
  The fault is that the SAME correct call happened twice, which no
  tool-interface change can prevent; the loop lives one layer up, in
  the orchestration deciding whether to make the call at all.
- **A prompt fix** ("please don't repeat yourself") cannot be relied
  on either: the model is the thing that forgot, so asking it more
  firmly not to forget is not a control, it's a hope.

Only the code layer — a de-duplication check evaluated over the actual
sequence of tool calls, independent of what the model believes it has
or hasn't done — can name the fault (`"check_referral_criteria called
again with identical arguments"`) at the exact turn it happens.

**4 — before/after: turns, tokens, cost, AND pass rate, across the
WHOLE evaluation set, not just one case.** The single-case table above
shows turns/tokens/cost for `REF-5602` specifically; the requirement
to show pass rate did not fall is answered separately, at full-set
scale: re-running all 55 cases/95 trials with action de-duplication
disabled globally (no forced loop — just the guard removed) gives
**95/95 (100%), identical to the guard-enabled baseline**
(`full_set_pass_rate_with_guard_disabled` in the saved evidence). The
scripted reference policy never naturally repeats an identical call on
its own, so the guard's *absence* is invisible on ordinary runs — which
is exactly what makes this failure mode dangerous, and exactly why a
deliberately forced repeat (the single-case demonstration above) is
needed to actually exercise it. Pass rate did not fall because,
without a forced repeat, nothing about this deletion changes any
run's behaviour at all.

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
- **The code layer** (step cap, budget ceiling, action de-duplication)
  bounds *run length and repetition*; this run is short (6 turns,
  inside the cap of 8), cheap, and repeats nothing — none of the three
  code-layer guardrails could ever fire here, because nothing about
  this run's *shape* is wrong. What is wrong is a *value* — the wrong
  `band` reaching `book_slot` — and no amount of turn-counting or
  repeat-detection looks at argument values at all.
- **A prompt fix** ("always double-check that the band you book with
  matches the band `check_referral_criteria` assessed, not a slot
  row's own label") is exactly the kind of fix this project
  deliberately rejects as unreliable: it is a sentence asking the
  calling logic to remember a distinction the interface itself no
  longer enforces. This project's own v1-vs-v2 prompt comparison
  (`docs/D5_MODEL_BATTERY.md`) already measured what happens when a
  prompt is the only thing standing between a model and an exact rule
  it must follow — v1 (rules stated less precisely) scored 41.1% where
  v2 (the same rule, structurally reinforced) scored 100%. A sentence
  can be forgotten, skipped, or misread on any given run; a Python
  function signature that no longer accepts a wrong `band` cannot be.

Only the interface itself — making `band` a **required, filtered**
argument so a wrong-band row can never be returned in the first place —
closes this, which is exactly the reasoning that made `band` required on
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
