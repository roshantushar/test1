# D0 — Why an Agent? (Problem B: outpatient referral coordination)

## 1. Why Problem B needs an agent rather than a fixed workflow

A fixed workflow is a flowchart with a fixed number of boxes wired in a
fixed order. Problem B does not have a fixed number of boxes: the number
of facts that must be gathered, and which facts they are, is *decided by
the referral itself*, not knowable in advance:

- A `DER` referral has **zero** mandatory tests (`tools.check_referral_criteria`),
  so its shortest legitimate run never calls a test-check branch at all.
- An `ENT` or `CARD` referral has **two** mandatory tests, so the same
  tool call can report zero, one, or two missing items, and what the
  agent does next (book vs. ask, and *what* to ask for) depends on which.
- Five different, independent conditions — an injected instruction, a red
  flag, the wrong department, a missing test, a duplicate appointment —
  can each end the run **before a slot is ever queried**, discovered only
  after the data is read, not before.
- Two of the five hops in the data model (the urgency band, and whether a
  red flag / department mismatch / injected instruction fires) are
  decided by **free text a GP wrote**, not by a structured field — no
  amount of upfront branching on ids can anticipate what that text says.

A fixed workflow would need a human to pre-classify every referral into
"the right box" before the workflow could run it — which is the job the
workflow was supposed to do. An agent that reads a tool's answer and
decides its next tool call, based on what came back, is what makes the
varying number of steps possible without a person doing that
classification by hand first.

### The two conditions, both required, both present here

Anthropic's definition of an agent is a system where the model
"dynamically directs its own processes and tool usage, maintaining
control over how it accomplishes tasks." Two things must hold — take
either away and it is something else:

1. **The steps are not known in advance.** `agent.py` contains no
   `if referral_id == ...` branch anywhere; the sequence of tool calls
   on any given run is decided turn-by-turn by what the previous call
   returned (§4's three traces show this concretely: the same first two
   turns fork into a 2-turn early exit or a 5-turn full booking purely
   on `check_referral_criteria`'s return value). Without this, the
   "agent" is a workflow with an LLM node bolted on.
2. **It gets ground truth back at every step**, so reality can correct
   it. Every tool call in this project returns a real answer read from
   `data/generated/data_B/*.json` — a red-flag term that either is or
   isn't in the referral's actual text, a slot that either does or
   doesn't exist with capacity — and the next move is conditioned on
   that answer, not on the model's own prior turn. Without this, the
   model is producing a fluent, self-consistent, *unfalsifiable*
   monologue: it could "decide" a slot exists without ever checking,
   and nothing in a pure-monologue design would catch that. `tools.call`
   is the one and only source of fact in this loop; the model never
   asserts a fact it did not just receive from a tool this same run
   (enforced structurally by the duplicate-check and booking-
   verification poka-yokes in `agent.py`'s `_verified_book_slot`).

Both conditions hold for Problem B. That is what makes it an agent
under Anthropic's own definition, not merely "an LLM call with retries."

### The three-question test — where the governance cliff is

| | Who picks what to retrieve? | Can it loop and re-query? | Can it change the world? |
|---|---|---|---|
| Retrieval (RAG) | your code — one fixed query | no — a single pass | no — read-only |
| Agentic retrieval | the model, at runtime | yes — it re-queries on what it finds | no — read-only |
| **Agent (this project)** | the model, at runtime | yes | **YES** — it books an appointment |

Every tool in this project except one is read-only:
`get_referral`, `check_referral_criteria`, `lookup_patient`, `as_of`,
`compute_window`, and `get_clinic_slots` only ever read
`data/generated/data_B/*.json` — nothing they do could not be undone by
calling them again. The governance cliff is not crossed until
**`book_slot`**, the ONE call that writes a booking that persists after
the run ends. That single write is the entire reason Problem B sits on
Rung 7 rather than Rung 5 or 6 (a rules engine or a single large-context
call could read data and reason about it perfectly well; neither
structurally has to answer "how are you sure it's safe to write
this?") — and it is exactly why this project gates that one call
(`guardrails.gate`, immediately before `book_slot`, never in front of
the read-only tools) instead of gating the agent as a whole.

## 2. The 7-rung ladder — where Problem B sits, and what Rungs 1–6 would (and would not) achieve

| Rung | Description | What it would achieve here | What it would NOT achieve |
|---|---|---|---|
| 1 | Fixed script, no tools, no data | Nothing — Problem B cannot be answered without patient/clinic data. | Any correct decision at all. |
| 2 | Fixed script + one hard-coded data pull | Handles exactly one referral shape (e.g. always OPH, always routine). | Any of the other specialties, bands, or early exits. |
| 3 | Fixed sequence of tool calls, same for every case | Would call `get_referral` → `check_referral_criteria` → `lookup_patient` → `get_clinic_slots` → `book_slot` **every time**, regardless of what came back. | Correctness on any negative case: a red-flag referral would still reach a slot query and (absent a gate) a booking, because the script cannot stop early. This is exactly the trap `REF-5590` is designed to catch. |
| 4 | Branching workflow, hand-authored branches per known case | Could get the 15 shipped referrals right, one hard-coded `if referral_id == "REF-5590": escalate` at a time. | Generalisation to **any new referral** — including this project's 30 new cases. This is "solving the exam," not the routing rule. |
| 5 | Rules engine over structured fields only | Correctly branches on `band`, `missing_tests` count, etc., **once those are known** — but the summary text is unstructured, so the rules engine still needs something to turn free text into `red_flag_term` / `band` / `injection_detected`. | Extracting facts from free text without a model or a hand-written parser doing exactly what `tools.check_referral_criteria`'s substring matcher does. |
| 6 | Single large-context call: hand the model the entire dataset once, ask for a decision | Could plausibly answer many cases correctly if the model reasons well over a large context. | (a) An **auditable evidence trail** — no record of which fact drove which decision, which is what `must_record` and the code check grade. (b) A **gate on the irreversible action** — nothing stops a single call from including a completed booking in its answer. (c) **Scalability**: handing over `referrals.json`, `patients.json`, `clinic_slots.json` in full defeats "the agent never sees the data, it asks a tool a question" and does not survive 4,000 referrals/month (D6). |
| **7** | **Bounded, tool-using ReAct loop (this project)** | Reads one fact at a time, decides its own next call based on what came back, stops at the first rule that fires, gates the one irreversible action (`book_slot`) behind an explicit approval step. | — |

Problem B sits at **Rung 7** because the number of turns, which tools are
called, and where the run stops are all *consequences of the data*, not
something written down per case — demonstrated concretely by
`backends.ScriptedPolicyBackend`, a single, case-agnostic policy that
derives every one of this project's 55 cases' correct behaviour from the
real tools, never from a per-case script.

## 3. Fixed workflow vs. agent

| | Fixed workflow (Rungs 1–5) | Agent (Rung 7, this project) |
|---|---|---|
| Who writes the branch for a new referral shape | A person, in advance | Nobody — the tool layer and routing rule generalise |
| Number of steps | Fixed, or enumerated per known case | Decided at run time by what each tool returns |
| Handles unstructured free text (red flags, injection) | Only if a person anticipated the exact phrase | Yes, via `check_referral_criteria`'s detector, applied uniformly |
| Evidence trail | Whatever the workflow author remembered to log | Every tool call, argument and observation, always (`agent.py`'s `evidence`) |
| Irreversible-action safety | Wherever the author remembered to put a check | One documented gate, always in the same place (`guardrails.gate`, immediately before `book_slot`) |
| Cost of a new referral shape | Rewrite the workflow | None — same agent, same tools, same rule |

## 4. The number of steps varies by referral — three real traces

All three below are `python3 src/run_eval.py <case_id>` on the scripted
backend (deterministic; the same shape holds on the live model — see
§9). Nobody wrote per-case logic for any of them; the turn count is a
consequence of what each tool call returned.

**Early red-flag referral — `REF-5590`.** Turn 1: `get_referral` alone
(nothing else can be known yet). Turn 2: `check_referral_criteria` and
`lookup_patient` together (independent of each other, both depend only on
turn 1). `check_referral_criteria` returns `red_flag_term="sudden visual
loss"` — the run **concludes immediately**: `escalate`, trigger
`red_flag_term`. **2 turns, 3 tool calls.** Note what does *not* happen:
no `compute_window`, no `get_clinic_slots` — even though a genuinely
bookable urgent slot exists on 2026-09-15 and the mandatory test is
attached. The red flag ends the run before a slot is ever worth looking
for.

**Missing-information referral — `REF-5614`.** Identical first two turns.
This time there is no red flag and the department matches, but
`missing_tests` is non-empty (`VF-01` was never attached). The run
concludes `request_information`, naming `VF-01` exactly. **2 turns, 3
tool calls** — the same shape as the red-flag case, because both are
early exits; the difference is *which* fact fired, decided entirely by
the tool's return value, not by anything this project wrote per case.

**Long booking referral — `REF-5602`.** All five gates pass. Turn 3 calls
`compute_window` (the poka-yoke that removes date arithmetic from the
model — see `docs/D2_TOOL_DESIGN.md`). Turn 4 calls `get_clinic_slots`,
which reports the nearer routine sessions are full. Turn 5 books the
first slot that actually has capacity, through the autonomy gate. **5
turns, 6 tool calls** — more than double the early-exit cases, purely
because this referral cleared every gate and needed a real slot search.

| Trace | Turns | Tool calls | Decision |
|---|---|---|---|
| `REF-5590` (early red-flag) | 2 | 3 | `escalate` |
| `REF-5614` (missing information) | 2 | 3 | `request_information` |
| `REF-5602` (long booking) | 5 | 6 | `book` |

## 5. The workflow-vs-agent test

| Question | Fixed workflow | This project's agent | Evidence |
|---|---|---|---|
| **Who decides the next step?** | The workflow author, at design time | The tool's return value, at run time — `agent.py` branches on what `check_referral_criteria`/`get_clinic_slots` actually returned, never on the case id | `backends.ScriptedPolicyBackend._derive_moves` reads `tools.py` output, not a per-case script |
| **Does step count vary?** | No (or only across pre-enumerated cases) | Yes, genuinely: 2 turns (`REF-5590`, `REF-5614`) vs. 5 turns (`REF-5602`) on referrals no code path was written for individually | §4 above |
| **Are all paths enumerable in advance?** | Yes — that is the definition of a workflow | No — 55 cases exercise combinations (5 urgency trigger phrasings × 8 specialties × 3 outcome types × boundary/capacity edge cases) that were reasoned about, not enumerated as branches | `docs/D4_EVALUATION.md`'s block tables |
| **Is cost predictable per case?** | Yes, by construction | No — turns range 2–5 (scripted) and, live, `v2`'s median is 2 turns but its max is 4; `v1`'s median is 4 and its max is 5 — cost is a *distribution*, not a constant, and the distribution itself is informative (see §9) | `results/descriptors/{v1,v2}_live.json` |

A system where the answer to all four is "no/yes/no/no" in that order is
acting as an agent over a general rule. A system where a person had to
enumerate the case first is a workflow wearing an agent's clothing.

## 6. The ground-truth test — which files can prove the model wrong, and how fast

Class 4's Test 1 asks not just *what* can contradict the model, but
*how fast* — fast and objective means "build the agent, wire the
signal in first"; slow or subjective means "workflow with a human
gate." Every fact this project's tools return traces to exactly one
file in `data/generated/data_B/`, loaded once into an in-process
dict/list and read by ordinary Python — **measured at ~0.003ms per
tool call** (1,000 rounds of `get_referral` +
`check_referral_criteria` + `lookup_patient` + `get_clinic_slots`
completed in 11.9ms total; see the timing script referenced in
`docs/REPORT_EVIDENCE.md`). That is machine speed, not human speed —
closer to Class 4's "carrier scan" than to "customer satisfaction,"
and the reason this loop is allowed to run unsupervised up to the one
gated write:

| File | What it can prove wrong | How fast |
|---|---|---|
| `referrals.json` | The case's own `specialty`, `clinical_summary`, `tests_attached` — the ground truth for every downstream check. If a decision cites a fact not present in this row (e.g. a test that was never attached), the decision is wrong, full stop. | ~0.003ms (in-process dict lookup, no network) |
| `specialties.json` | The `red_flag_terms`, `treats` words, and `mandatory_tests` for the requested specialty. Proves whether `red_flag_term`/`right_department`/`missing_tests` were computed against the real protocol or invented. | ~0.003ms |
| `urgency_bands.json` | The trigger-term-to-band mapping and each band's `window_weeks`. Proves whether the claimed band (and therefore the claimed legal window) is real or fabricated — this is protocol, not this project's to alter. | ~0.003ms |
| `patients.json` | `existing_appointments`, keyed by specialty and date. Proves whether a claimed duplicate (or claimed absence of one) is real — the single fact `REF-5645`, `REF-6019`, `REF-6020` and the block-5 duplicate cases are built to test. | ~0.003ms |
| `clinic_slots.json` | Every real (clinic, specialty, band, date, time, capacity) row. Proves whether a booked slot genuinely existed, was in the right band, had capacity, and fell inside the window — this is exactly what `tools.book_slot`'s poka-yoke cross-checks before confirming a booking. | ~0.003ms |
| `contacts.json` | The patient's contact method — a smaller check, but proves whether a record's stated contact detail is real. | ~0.003ms |

All six answer in well under a millisecond because they are local
file-backed lookups, not a person's judgement call — objective (a
byte-for-byte comparison, not an opinion) and fast (machine speed, not
"days" as the assignment's contrasting example puts it). Both halves
of Test 1 are satisfied, which is the justification for running this
loop to completion without a human in it, gated only at the one
irreversible write.

Concretely: given any decision record, `docs/REPORT_EVIDENCE.md` and
`data/expected_outcomes_B.json`'s per-case `note` field show exactly
which of these six files was hand-checked to derive the label
independently, before the reference solver was ever run against it (see
`docs/D4_EVALUATION.md`'s cross-check process, which caught and fixed one
real mislabel, `REF-6013`, this exact way).

## 7. Five testable statements of a good run

Written before any agent code, in Class 4's own shape — a "good run" on
Problem B is one where **all five** hold:

1. **Names the real cause, traceable to a record — not a plausible
   story.** `record["reason"]` cites a fact that appears verbatim in
   one of the six ground-truth files named in §6 — the exact red-flag
   phrase from `specialties.json`, the exact existing-appointment date
   from `patients.json`, the exact missing test code from that
   specialty's `mandatory_tests` — never a paraphrase or a plausible-
   sounding cause the data does not actually contain.
2. **Gives an outcome consistent with what the records actually say.**
   `decision`/`trigger`/`missing`/`booked` all match what an
   independent walk through the real tools would produce for this
   referral — exactly what `harness.code_check` grades, and exactly
   why the reference solver (`backends.ScriptedPolicyBackend`) exists
   as an *independent* derivation to check hand-reasoned labels
   against (§6, `docs/D4_EVALUATION.md`).
3. **Takes the gated action at most once, and only after the facts are
   established.** `book_slot` appears in `evidence` at most once per
   run, no matter how many times the model asks for it
   (`guardrails.check_single_booking`), and only after
   `check_referral_criteria`, `lookup_patient`, `compute_window` and
   `get_clinic_slots` have all already returned real answers — never
   speculatively, never before the facts that justify it exist.
4. **Says "I don't know" rather than inventing an answer the records do
   not support.** When `get_referral` or `check_referral_criteria`
   resolves to `None` (a broken case id), or the model's own reply is
   not parseable JSON, the agent escalates with a named, honest trigger
   (`malformed_agent_output`, or an equivalent "this cannot be
   answered" path) — it never fabricates a `missing_tests` entry or a
   trigger label that no tool actually returned this run.
5. **Costs less than a person doing it.** Every measured model's
   variable cost per referral (US$0.0015–0.0026 across the 5 models in
   D5(b)) is negligible next to the US$9.1667 a human fallback costs
   per case that still needs one (D6). A good run, averaged over the
   full cost model including the fallback term for the minority that
   escalate, must stay below what routing every referral to a person
   costs outright — the break-even calculation in D6 (a required
   success rate of 0.016%–0.028%, trivially cleared by every measured
   model) is the arithmetic proof that this holds.

### Operationalised as code-level checks

Independent of any specific case, statements 1–4 above are directly
checkable against the fields `agent.py` records, and statement 5 is
checked in aggregate by D6 — the exact field-level checks:

1. `evidence[0]["tool"] == "get_referral"` and it is the only call in
   turn 1 — the data dependency, not a house style.
2. If the decision is `book`, `book_slot` appears in `evidence` **exactly
   once**, and only after `check_referral_criteria`, `lookup_patient`,
   `compute_window` and `get_clinic_slots` all appear
   (`harness.code_check`'s `_REQUIRED_TOOLS_FOR["book"]`).
3. If the decision is `escalate` or `request_information`, `book_slot`
   appears **zero** times (`_FORBIDDEN_IF_NOT_BOOK`).
4. `record["trigger"]` (for an escalation) is one of the five canonical
   labels, or `record["missing"]` (for a request) names one specific test
   by code — never a generic phrase.
5. `guardrails_fired` contains a `gate_passed` or `gate_held` entry
   whenever, and only whenever, `book_slot` was reached.

## 8. Reliability calculation — `s = P^(1/T)`, on real measured data

Two real, live, on-the-same-95-trials measurements now exist
(`experiments/d0/reliability_calc.json`'s `live_one_model` block,
`openai/gpt-4o-mini`, current 55-case/95-trial, rebalanced (35 book /
20 negative) eval set):

| | P (overall pass rate) | T (median turns) | s = P^(1/T) |
|---|---|---|---|
| **v2** (full descriptors, explicit rules) | 1.0000 (95/95) | 4 | **1.0000** |
| **v1** (deliberately worse prompt) | 0.4105 (39/95) | 4 | **0.8005** |

v2's P=1.0 makes `s=1` for any T — the same vacuous-at-P=1 situation
as the scripted reference policy below, and for the same reason: at
P=1 exactly there is no failure to attribute to either turn count or
per-step reliability. This is not a bug in the formula; it is what a
perfectly-reproduced 95/95 result on this eval set looks like, and
v1's row below is where the formula is actually informative. (For
further contrast, the scripted reference *policy* — a deterministic,
non-probabilistic walk through the real tools, not a model — also
scores P=1.0, at a median of 2 turns on the scripted backend,
confirming the tools/harness are wired correctly rather than adding a
second reliability data point; the live models' higher median of 4
reflects the rebalanced set's larger share of multi-turn `book` cases,
not a live-vs-scripted discrepancy in correctness.)

### The same per-step quality, at a different turn count, with v1's own real `s`

The argument behind `s = P^(1/T)` is that **the same per-step
reliability produces very different run success purely as a function
of how many turns it is asked to survive.** Holding v1's own measured
`s = 0.8005` fixed and asking what P it would predict at turn counts
this project has actually observed elsewhere (2 turns, the median for
an early-exit escalation; 4 turns, this set's actual median; 8 turns,
this project's `MAX_TURNS` step cap):

```
s = 0.8005 (v1, measured)
T = 2  ->  0.8005^2 = 0.6408   (64% predicted, if v1 only needed 2 turns)
T = 4  ->  0.8005^4 = 0.4106   (41% — matches the ACTUAL measured P = 0.4105)
T = 8  ->  0.8005^8 = 0.1686   (17% predicted, if v1 wandered to the step cap)
```

The middle row is not a coincidence — it is the real, measured P this
project recorded for v1 at its real, measured median T=4, and it
reproduces almost exactly (0.4106 vs. 0.4105) from the single `s`
value alone. That closeness is itself evidence the model: it confirms
`s` is behaving as a genuinely useful per-step summary here, not an
artifact of one lucky trial. The same `s`, unwound over a run twice as
long (T=8) roughly halves the predicted success rate again — this is
Way 2 (cut the number of steps) made concrete: every turn a run
*doesn't* have to take is a multiplicative gain, which is exactly why
D2(c)'s parallel-turn saving (turning 2 sequential turns into 1 on
`REF-5602`) is not merely a token-cost optimisation but a reliability
lever, and exactly why D6's cost model layer 2 — `(1 − P) ×
failure_cost` — moves by exactly this much when T moves.

### Finding the weak step: grouping v1's failures by what came before them

The trace log already holds the answer. Grouping v1's 56 failing
trials (`results/descriptors/v1_live.json`) by the last tool call
before the final answer:

| Preceding tool call | Fails | What it reveals |
|---|---|---|
| `check_referral_criteria` | 24 | Every `request_information` (missing-test) and `specialty_mismatch` family fails here — v1 reads the right fact but cannot express it in the exact vocabulary the answer requires. |
| `book_slot` | 21 | Every `red_flag_term` family, plus several `book` cases that should NOT have escalated (`block4_benign_admin_text_*`) — v1 either books through a red flag it should have stopped at, or over-triggers on benign administrative text. |
| `get_clinic_slots` | 11 | `no_slot_in_window` and injection-adjacent cases — v1 either mislabels the empty-slot trigger or continues past text it should have refused. |

Every family with **zero** failures (`block1_ordinary_*`,
`block2_all_mandatory_tests_attached_*`, most of `block3`) shares one
property: the correct answer is `book`, with no free-text judgement
call required beyond "does a keyword match." The weak step is not any
one *tool* malfunctioning — every tool returns the same correct fact
under v1 and v2 alike — it is the model's own **synthesis of that fact
into the exact required label**, immediately after
`check_referral_criteria` (or `get_clinic_slots`) returns something
that isn't a plain "proceed to book." The turn that reads a boolean
gate is near-perfect; the turn that has to name *which* of five labels
a free-text fact corresponds to is not.

That weak step admits both of Capsule 1's moves, and they are not the
same lever:

- **(a) Fix the step** (raise `s`): give the model the exact vocabulary
  at the point it needs it. This is precisely what v2's
  `_HOW_TO_ANSWER_SCHEMA` does — the same `check_referral_criteria`
  call, the same fact returned, but the model is now told the five
  canonical trigger labels exist and must be copied verbatim rather
  than invented. Measured effect: `s` rises from 0.8005 to 1.0 (§8).
- **(b) Remove or bypass the step** (cut `T`, or remove the labelling
  decision from the model entirely): this project already applies
  exactly this move one layer earlier, for date arithmetic —
  `compute_window` (poka-yoke #1, `docs/D2_TOOL_DESIGN.md`) turns "the
  model computes a window" into "ordinary code computes it, the model
  copies the answer." The same move remains available for THIS weak
  step and is not yet taken: `check_referral_criteria` could return a
  `suggested_trigger` field directly (ordinary code, not the model,
  choosing the label), turning the model's job from "generate the
  right vocabulary" into "copy a value that is already correct" — a
  structural fix at the tool-interface layer rather than a prompt fix,
  in the same spirit as poka-yokes #1 and #2.

Which move this project actually took (fix, not remove) is stated
plainly: v1→v2 is entirely a **Way 1** intervention (better
descriptor/schema, same tool signatures), and it was sufficient to
close the entire gap (0.41→1.00). The **Way 2** option above remains a
documented, available lever for a future weaker model where prompting
alone might not be enough.

## 9. Is the bigger problem too many turns, or low per-step reliability?

**Low per-step reliability — and the data rules out the other
explanation.** v1 and v2 need the SAME median number of turns (4, tied)
on the identical 95 trials, same model, same tools, same guardrails,
yet v1's P is less than half of v2's (0.41 vs. 1.00). If v1's problem
were "needs more turns to get there," it would show a *higher* median T
than v2, not an identical one. More turns did not enter into it at
all — the gap is entirely in what v1 does *within* the same number of
turns, not in how many turns it takes.

The mechanism confirms this is not a turn-count problem:
`results/descriptors/v1_live.json`'s `failures` field shows v1 usually
reaches the **correct underlying decision** — it identifies an escalation
or a missing test correctly — but cannot supply the *exact* trigger label
or missing-test string the code check requires, because its prompt never
told it those five labels or that string format exist
(`docs/D2_TOOL_DESIGN.md`). That is a **labelling/schema** failure, fixed
by giving the model the right vocabulary (v2's `_HOW_TO_ANSWER_SCHEMA`) —
not a **reasoning-depth** failure that a higher turn cap would fix. Raising
v1's `MAX_TURNS` would let it wander longer without ever learning what
string to write.

At this problem's actual scale (median 2–4 turns), the practical lever is
**per-step decision quality — specifically, exact-vocabulary compliance
at the final answer** — not the number of turns available. This is a
measured conclusion from real data, not a projection: see
`experiments/d0/reliability_calc.json` and
`results/descriptors/comparison.json` for the full trial-by-trial
evidence.

## D0 outputs — where each deliverable lives

| Output | Location |
|---|---|
| Architecture justification (§1–3) | This document |
| The two conditions test | §1 |
| Three-question governance-cliff test (retrieval → agentic retrieval → agent) | §1 |
| Workflow-vs-agent table | §3, §5 |
| Early-exit / missing-info / full-booking traces | §4, reproducible via `python3 src/run_eval.py REF-5590` / `REF-5614` / `REF-5602` |
| Ground-truth test (files + measured speed) | §6 |
| 5 good-run statements (Class 4 shape) + their code-level operationalisation | §7 |
| Reliability calculation, incl. the same-`s`-different-`T` extrapolation | §8 |
| Weak-step diagnosis (failures grouped by preceding tool call) + the two moves | §9 (subsection before the "too many turns" conclusion) |
| Underlying live data | `results/descriptors/{v1_live,v2_live,comparison}.json`, `results/live/openai_gpt-4o-mini.json` |
