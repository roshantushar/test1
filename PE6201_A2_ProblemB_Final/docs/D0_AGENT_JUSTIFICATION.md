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
derives every one of this project's 45 cases' correct behaviour from the
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
| **Are all paths enumerable in advance?** | Yes — that is the definition of a workflow | No — 45 cases exercise combinations (5 urgency trigger phrasings × 8 specialties × 5 outcome types × boundary/capacity edge cases) that were reasoned about, not enumerated as branches | `docs/D4_EVALUATION.md`'s 30-case block table |
| **Is cost predictable per case?** | Yes, by construction | No — turns range 2–5 (scripted) and, live, `v2`'s median is 2 turns but its max is 4; `v1`'s median is 4 and its max is 5 — cost is a *distribution*, not a constant, and the distribution itself is informative (see §9) | `results/descriptors/{v1,v2}_live.json` |

A system where the answer to all four is "no/yes/no/no" in that order is
acting as an agent over a general rule. A system where a person had to
enumerate the case first is a workflow wearing an agent's clothing.

## 6. The ground-truth test — which files can prove the model wrong

Every fact this project's tools return traces to exactly one file in
`data/generated/data_B/`, and no decision is defensible without citing
the specific row that produced it:

| File | What it can prove wrong |
|---|---|
| `referrals.json` | The case's own `specialty`, `clinical_summary`, `tests_attached` — the ground truth for every downstream check. If a decision cites a fact not present in this row (e.g. a test that was never attached), the decision is wrong, full stop. |
| `specialties.json` | The `red_flag_terms`, `treats` words, and `mandatory_tests` for the requested specialty. Proves whether `red_flag_term`/`right_department`/`missing_tests` were computed against the real protocol or invented. |
| `urgency_bands.json` | The trigger-term-to-band mapping and each band's `window_weeks`. Proves whether the claimed band (and therefore the claimed legal window) is real or fabricated — this is protocol, not this project's to alter. |
| `patients.json` | `existing_appointments`, keyed by specialty and date. Proves whether a claimed duplicate (or claimed absence of one) is real — the single fact `REF-5645`, `REF-6019`, `REF-6020` and the block-5 duplicate cases are built to test. |
| `clinic_slots.json` | Every real (clinic, specialty, band, date, time, capacity) row. Proves whether a booked slot genuinely existed, was in the right band, had capacity, and fell inside the window — this is exactly what `tools.book_slot`'s poka-yoke cross-checks before confirming a booking. |
| `contacts.json` | The patient's contact method — a smaller check, but proves whether a record's stated contact detail is real. |

Concretely: given any decision record, `docs/REPORT_EVIDENCE.md` and
`data/expected_outcomes_B.json`'s per-case `note` field show exactly
which of these six files was hand-checked to derive the label
independently, before the reference solver was ever run against it (see
`docs/D4_EVALUATION.md`'s cross-check process, which caught and fixed one
real mislabel, `REF-6013`, this exact way).

## 7. Five testable statements of a good run

Independent of any specific case, a "good run" on Problem B is one where
**all five** hold — each is directly checkable against the fields
`agent.py` records:

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

Two real, live, on-the-same-107-trials measurements now exist
(`experiments/d0/reliability_calc.json`'s `live_one_model` block,
`openai/gpt-4o-mini`, current 45-case/107-trial eval set):

| | P (overall pass rate) | T (median turns) | s = P^(1/T) |
|---|---|---|---|
| **v2** (full descriptors, explicit rules) | 1.0000 (107/107) | 2 | **1.0000** |
| **v1** (deliberately worse prompt) | 0.2710 (29/107) | 4 | **0.7215** |

v2's P=1.0 makes `s=1` for any T — the same vacuous-at-P=1 situation
as the scripted reference policy below, and for the same reason: at
P=1 exactly there is no failure to attribute to either turn count or
per-step reliability. This is not a bug in the formula; it is what a
perfectly-reproduced 107/107 result on this eval set looks like, and
v1's row below is where the formula is actually informative. (For
further contrast, the scripted reference *policy* — a deterministic,
non-probabilistic walk through the real tools, not a model — also
scores P=1.0 at a median of 2 turns, confirming the tools/harness are
wired correctly rather than adding a second reliability data point.)

## 9. Is the bigger problem too many turns, or low per-step reliability?

**Low per-step reliability — and the data rules out the other
explanation.** If v1's problem were merely "needs more turns to get
there," it would show *higher* P at a *higher* T. Instead v1 has **both**
a higher median turn count (4 vs. 2) **and** a much lower P (0.27 vs.
1.00) than v2, on the identical 107 trials, same model, same tools, same
guardrails. More turns did not buy v1 more reliability — it bought
neither.

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
| Workflow-vs-agent table | §3, §5 |
| Early-exit / missing-info / full-booking traces | §4, reproducible via `python3 src/run_eval.py REF-5590` / `REF-5614` / `REF-5602` |
| Reliability calculation | §8, `experiments/d0/reliability_calc.py` → `experiments/d0/reliability_calc.json` |
| 5 good-run criteria | §7, enforced by `harness.code_check` |
| Ground-truth file map | §6 |
| Underlying live data | `results/descriptors/{v1_live,v2_live,comparison}.json`, `results/live/openai_gpt-4o-mini.json` |
