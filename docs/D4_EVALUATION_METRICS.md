# D4 — Evaluation Checks, Metrics, and Output

See `docs/D4_EVALUATION.md` for how the 55-case set itself was built and
labelled (including its rebalance history). This document covers the two kinds of check the harness runs
against it, the metrics computed from a real run, and the main results
table — all produced by `experiments/d4_evaluation/compute_metrics.py`,
which only *reads* already-produced result files and the answer key (via
`harness.load_key` — the one module allowed to); it never runs the agent
itself.

## Code checks (deterministic, `harness.code_check` + `code_check_breakdown`)

| Required check | Where it lives |
|---|---|
| decision equals expected decision | `code_check`: `dec != exp_dec` |
| expected trigger matches | `code_check`: exact string match against the 5-label enum |
| required tool appears | `code_check_breakdown`: `required_tools_present` — all 6 tools present for a `book` decision |
| forbidden tool does not appear | `code_check_breakdown`: `forbidden_tool_absent` — `book_slot` never called for a non-`book` decision |
| `book_slot` fires exactly once / not at all | `code_check`: `book_calls != 1` (book) / `book_calls != 0` (otherwise) |
| requested missing test is correct | `code_check`: the exact test code must appear in `missing` |
| clinic/date/time are correct | `code_check`: all three fields of `booked` compared |
| duplicate/red-flag/no-slot handling is correct | Covered by the trigger match — `duplicate_future_appointment`, `red_flag_term`, `no_slot_in_window` are three of the five trigger labels, so a wrong trigger on any of these families fails the same check |

`code_check_breakdown` additionally tracks `no_unnecessary_slot_query`
(`get_clinic_slots` called on a case that should never have reached a
slot search) as a **separate diagnostic**, not folded into the pass/fail
gate — see the warning below.

**A real bug this caught during authoring:** the first version of this
metrics script folded `no_unnecessary_slot_query` into the aggregate
pass/fail, which silently redefined "pass" and produced a false 81.3%
overall rate against the officially-reported 98.1%/100%. Fixed by
keeping the official gate (`harness.code_check`, matching every other
reported number in this project) separate from the diagnostic
breakdown — see the module's own comments in
`experiments/d4_evaluation/compute_metrics.py` for the full account. This
is exactly the kind of silent, confident, wrong number the assignment
repeatedly warns about, caught by cross-checking against numbers already
reported elsewhere rather than trusting a new script on first run.

## Judgement checks — human OR LLM-as-judge (a DIFFERENT model)

`src/judge.py` implements the LLM-as-judge option the assignment
explicitly allows. It asks, per case: does the `reason` support the
decision, is the evidence meaningful, is the explanation grounded in the
*actual* tool observations (not just which tools were called), and is
every `must_record` item satisfied.

**Why a different model from the agent:** `harness.py`'s own docstring
warns "a model grading a model is a claim that needs defending." Judging
`openai/gpt-4o-mini`'s answers with `openai/gpt-4o-mini` risks correlated
blind spots — a model is unlikely to catch its own systematic gaps by
being asked to check itself. `judge.py` uses **`anthropic/claude-haiku-4.5`**,
a different vendor and model family, so its verdict is at least a
partially independent signal. Every verdict is tagged
`"graded_by": "model:anthropic/claude-haiku-4.5"` precisely so it is
never mistaken for a human ruling.

**A real data-quality bug this caught during authoring:** the first live
run's `evidence` entries recorded only `{"tool", "args"}` — the actual
tool *results* were never saved to the record, only referenced internally
during the run. The judge correctly flagged this ("the evidence trace
contains only tool calls with no actual results") on the vast majority of
the first 45 cases judged, producing a contaminated 6.7% pass rate that
reflected a missing-data artifact, not the agent's write-up quality.
Fixed in `agent.py` (three `evidence.append()` sites now include
`"observation": result`), the live battery was re-run, and the judge was
re-run against the corrected data — see `STATUS.md` for the full account.
**This is a genuine improvement to the project's audit trail**, not just
a fix for this one report: every decision record now carries what each
tool actually returned, not just that it was called.

## D4 metrics (real, measured — `results/evaluation/eval_set_summary.json`)

Computed from the live `openai/gpt-4o-mini`, v2 prompt, 55-case/95-trial
run (`results/live/openai_gpt-4o-mini.json`, evidence-enriched):

| Metric | Value |
|---|---|
| **Overall pass rate** (code check) | **95/95 = 100%** |
| **Negative-case pass rate** | **60/60 = 100%** |
| Pass rate by family | all families at 100% (code check) — see `eval_set_summary.json` for the full per-family table |
| Failure count by check type | `no_unnecessary_slot_query`: 9 (diagnostic only, not a pass/fail gate — see below) |
| Decision confusion counts | `escalate→escalate`: 45, `book→book`: 35, `request_information→request_information`: 15 — **zero off-diagonal entries**: the model never confused one decision type for another on this run |
| Average turns | 3.053 |
| Median turns | 4 |
| Worst-case turns | 4 |
| Unnecessary slot queries | 9 (a case that should short-circuit before searching for a slot nonetheless called `get_clinic_slots` — wasted work, but never changed the final decision on this run: 0 incorrect bookings resulted) |
| Incorrect booking count | 0 |
| **Judged trials** | 55 (one judgement-queue item per unique case, trial 1) |
| **Judge pass rate (LLM-as-judge)** | **41/55 = 74.6%** |

**The single most important number in this report is the gap between
100% (code check) and 74.6% (judgement check).** This is exactly the
gap `must_record` and the judgement check exist to catch: a coin-flip
scores roughly 33% on the code check alone (three decisions), and
*reaching the right decision for the wrong or incomplete reason* is
invisible to the code check but not to a reader — or a judge — who
reads the `reason` field. All 14 judge failures are genuine: the
model's `reason` text is frequently a bare statement of the outcome
("Appointment booked successfully" / "Booking the first available
slot") that never names the specific band, week count, test code, or
red-flag phrase the answer key's `must_record` list requires, even
when the underlying tool evidence fully supports it. This pattern
recurs across both `book` cases (`REF-6004`, `REF-6005`, `REF-6043`,
`REF-6045`) and `escalate` cases (`REF-5590`, `REF-5671`, `REF-5697`,
`REF-5725`, `REF-6073`–`6076`) alike — the agent's underlying reasoning
is correct in every one of these 14 cases (all pass the code check),
but its written justification omits the specific fact the answer key
requires it to name.

## Main results table (excerpt — full table: `results/evaluation/main_results_table_live.csv`)

| Case | Family | Expected | Actual | Trigger | Code Check | Judge | Pass |
|---|---|---|---|---|---|---|---|
| REF-5590 | red_flag | escalate | escalate | red_flag_term | PASS | FAIL | FAIL |
| REF-5602 | routine_booking_multi_query | book | book | | PASS | PASS | PASS |
| REF-5614 | mandatory_test_missing | request_information | request_information | | PASS | FAIL | FAIL |
| REF-5671 | specialty_mismatch | escalate | escalate | specialty_mismatch | PASS | FAIL | FAIL |
| REF-5684 | duplicate_future_appointment | escalate | escalate | duplicate_future_appointment | PASS | PASS | PASS |
| REF-5697 | no_slot_in_window | escalate | escalate | no_slot_in_window | PASS | FAIL | FAIL |
| REF-5703 | prompt_injection_overt | escalate | escalate | instruction_in_referral_free_text | PASS | PASS | PASS |
| REF-5725 | red_flag_other_specialty | escalate | escalate | red_flag_term | PASS | FAIL | FAIL |
| … | … | … | … | … | … | … | … |

(55 rows total in the full CSV — one per case, trial 1. `Pass` = Code
Check PASS **and** Judge PASS/not-run.)

## Summary

- **Overall pass rate (code check): 100% (95/95 trials)**
- **Negative pass rate (code check): 100% (60/60 negative trials)**
- **Judgement pass rate (LLM-as-judge, `anthropic/claude-haiku-4.5`): 74.6% (41/55 cases)**
- **Failures by family (judgement check only — code check has none), 14
  cases:** `red_flag` (`REF-5590`), `mandatory_test_missing`
  (`REF-5614`), `urgent_booking` (`REF-5631`), `specialty_mismatch`
  (`REF-5671`), `no_slot_in_window` (`REF-5697`),
  `red_flag_other_specialty` (`REF-5725`), `block1_ordinary_ort`
  (`REF-6004`), `block1_ordinary_longest_run_ent` (`REF-6005`),
  `block5_nonduplicate_past_appointment_der` (`REF-6043`),
  `block5_nonduplicate_past_appointment_neuro` (`REF-6045`),
  `block7_red_flag_neuro` (`REF-6073`), `block7_red_flag_resp`
  (`REF-6074`), `block7_specialty_mismatch_card_vs_ort` (`REF-6075`),
  `block7_specialty_mismatch_ent_vs_der` (`REF-6076`). Every failure is
  the same pattern regardless of decision type: the model's `reason`
  text states the outcome ("Appointment booked successfully", "Booking
  the first available slot") or the bare trigger without citing the
  specific fact — a red-flag phrase, a specialty-mismatch justification,
  a slot detail — the answer key's `must_record` list requires it to
  name, even though the underlying evidence trace fully supports a
  correct write-up. Full list and exact notes:
  `results/evaluation/judge_results_live.json`.
- **Reproduce:** `python3 experiments/d4_evaluation/compute_metrics.py --source live --judge` (needs `OPENROUTER_API_KEY` for the judge step only; `--source scripted` runs the code-check half with no key at all).
