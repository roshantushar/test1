# PE6201 A2 — Problem B (Final): Outpatient Referral Coordination

A bounded, tool-using ReAct agent that reads one outpatient referral at a
time and returns exactly one of `book` / `request_information` / `escalate`,
gating the one irreversible action (`book_slot`) behind an autonomy check.
Built from scratch in this folder after studying the official read-only
scaffold at `../A2_scaffold 2/` — see "Relationship to the scaffold" below.

## Quick start — anyone can run this in under a minute

**Requirements:** Python 3.9 or later. Nothing else — no `pip install`,
no API key, no network. Verified against a clean copy of just this
folder, with no sibling directories present.

```bash
git clone <this repo's URL>
cd PE6201_A2_ProblemB_Final

python3 data/make_fixtures_B_final.py   # one-time: writes data/generated/data_B/*.json
python3 data/check_my_data_final.py     # must print "Data hangs together."

cd src
python3 run_eval.py                     # the full 55-case/95-trial scripted run
```

That last command reproduces this project's headline result — **95/95
trials pass the code check, zero step-cap hits** — with no key and no
network, writing `results/scripted/final_eval.json`. Every other
deliverable's command is listed in "D0–D7 experiment commands" and
"Result locations" further down; the only commands that need an
`OPENROUTER_API_KEY` are the two under "Live backend setup" below.

## Project layout

```
PE6201_A2_ProblemB_Final/
├── src/                 config, tools, backends, agent, guardrails,
│                        harness, prompt, run_eval, demo_loop_failure
├── data/                the EXTENDED, project-owned fixture generator,
│                        checker, and answer key (55 cases, 35 book /
│                        20 negative (36.4%) - see docs/D4)
├── experiments/         one folder per deliverable (d0, d2a…d2c, d3…d7)
├── results/             every experiment's saved JSON evidence
├── notebooks/           a guided tour notebook (exploration only)
├── docs/                D0–D7 write-ups + a report-evidence index
├── README.md, STATUS.md, requirements.txt
```

## Relationship to the read-only scaffold

`../A2_scaffold 2/` and `../A2_reference_data/` are **never modified** by
this project. Every module in `src/` was written after reading the
scaffold's equivalent file in full; each module's own docstring says
explicitly what idea was reused and what was changed and why (e.g.
`src/tools.py`'s docstring on the two new poka-yoke mechanisms,
`src/backends.py`'s docstring on why the scripted backend is a reference
*policy* over the real tools rather than a hand-typed transcript per case).
`data/make_fixtures_B_final.py` reproduces the shipped constants
byte-for-byte (verified — see below) and extends only the `EXTRA_*` lists,
exactly as the shipped generator's own comments instruct. Nothing under
`src/`, `data/`, `experiments/` or `results/` writes to any path under
`../A2_scaffold 2/` or `../A2_reference_data/`.

## Setup

Python 3, standard library only — no `pip install` needed for anything
scripted (see `requirements.txt`).

```bash
cd PE6201_A2_ProblemB_Final
python3 data/make_fixtures_B_final.py       # writes data/generated/data_B/*.json
python3 data/check_my_data_final.py         # validates - must print "Data hangs together."
```

## Validating the data

`check_my_data_final.py` is a copy of the official checker (validation
rules unchanged) pointed at this project's extended data. It checks: every
id resolves, no shipped row was edited or deleted (fingerprinted), no
duplicate ids, and every referral has exactly one answer-key label. It
currently reports **zero warnings, zero failures** over 55 referrals, 8
specialties (5 shipped + `NEURO`, `RESP` and `ENDO`, new), 30 clinic slots,
47 patients.

To independently re-verify that every shipped row is untouched:

```bash
python3 - <<'EOF'
import json, os
shipped, gen = "../A2_reference_data/data_B", "data/generated/data_B"
for t, k in [("referrals","referral_id"),("patients","patient_id"),
             ("specialties","code"),("contacts","patient_id")]:
    s = {r[k]: r for r in json.load(open(os.path.join(shipped, t+".json")))}
    g = {r[k]: r for r in json.load(open(os.path.join(gen, t+".json")))}
    assert all(g.get(k) == v for k, v in s.items()), t
print("all shipped rows byte-identical")
EOF
```

## One-case scripted run

```bash
cd src
python3 run_eval.py REF-5602      # every turn shown, decision record, code check
python3 run_eval.py REF-5614      # request_information anchor
python3 run_eval.py REF-5590      # escalate anchor
python3 run_eval.py --prompt      # exactly what a LIVE model would be told (v2)
python3 run_eval.py --prompt --v1 # the deliberately worse v1 descriptor set
```

## Full scripted run (D5a — what a marker runs)

```bash
cd src
python3 run_eval.py
```

No key, no network, no arguments (beyond the one-time
`make_fixtures_B_final.py` above). Writes `results/scripted/final_eval.json`.
**Current result: 95/95 trials passed (100%)**, median 2 turns, worst
case 5, zero step-cap hits.

## Live backend setup (D2b, D5b)

The full D5(b) live battery is complete: **5 models, 95 trials each, real
OpenRouter usage, on the identical 55-case eval set** —
`results/live/model_comparison.json`, `docs/D5_MODEL_BATTERY.md`.
Headline: `openai/gpt-4o-mini` 100%, `google/gemini-2.5-flash-lite` 95.8%,
`qwen/qwen-2.5-72b-instruct` 83.2%, `meta-llama/llama-3.1-8b-instruct`
52.6%, `mistralai/mistral-nemo` 21.1%. D2(b)'s required v1-vs-v2 whole-prompt
comparison, held to `openai/gpt-4o-mini` only, is also complete:
**v1 41.1% (39/95) vs v2 100% (95/95)** — see `results/descriptors/`,
`docs/D2_TOOL_DESIGN.md` and `STATUS.md` for the full account of what was
found and fixed along the way. To reproduce or extend either:

```bash
export OPENROUTER_API_KEY='sk-or-...'
# edit src/config.py:  BACKEND = "live"
python3 experiments/d2b_descriptors/run_live_comparison.py
python3 experiments/d5_models/run_live_battery.py   # edit MODELS list first
```

Both scripts fail loudly with these exact instructions if run without a key
— they do not silently fall back to fabricated numbers.

## Result locations

| Deliverable | Command | Result file(s) |
|---|---|---|
| D0 reliability calc | `python3 experiments/d0/reliability_calc.py` | `experiments/d0/reliability_calc.json` |
| D2(c) parallelism | `python3 experiments/d2c_parallelism/run_comparison.py` | `results/parallelism/{sequential,parallel,comparison}.json` |
| D3(b) guardrails | `python3 experiments/d3_guardrails/run_guardrail_cases.py` | `results/guardrails/guardrail_results.json` |
| D4/D5(a) full eval | `python3 src/run_eval.py` | `results/scripted/final_eval.json` |
| D6 cost model | `python3 experiments/d6_cost/run_cost_model.py` | `results/cost/d6_*.json` |
| D7 failure 1 (loop) | `python3 experiments/d7_failures/failure_1_loop.py` | `results/d7/failure_1_loop.json` |
| D7 failure 2 (interface) | `python3 experiments/d7_failures/failure_2_slot_interface.py` | `results/d7/failure_2_slot_interface.json` |
| D2(b) live v1-vs-v2 | `python3 experiments/d2b_descriptors/run_live_comparison.py` | `results/descriptors/*.json` |
| D5(b) live 5-model battery | `python3 experiments/d5_models/run_live_battery.py` | `results/live/*.json` |

See `docs/REPORT_EVIDENCE.md` for a claim-by-claim index tying every number
in the docs to the file and command that produced it.

## D0–D7 experiment commands (all in one place)

```bash
python3 data/make_fixtures_B_final.py
python3 data/check_my_data_final.py
python3 experiments/d0/reliability_calc.py
python3 src/run_eval.py --prompt              # D2b artefact (scripted, no live call)
python3 experiments/d2c_parallelism/run_comparison.py
python3 experiments/d3_guardrails/run_guardrail_cases.py
python3 src/run_eval.py                       # D4 + D5a
python3 experiments/d6_cost/run_cost_model.py
python3 experiments/d7_failures/failure_1_loop.py
python3 experiments/d7_failures/failure_2_slot_interface.py
# live-only, needs a key:
python3 experiments/d2b_descriptors/run_live_comparison.py
python3 experiments/d5_models/run_live_battery.py
```

## Limitations

- **The autonomy gate's `approve()` callback auto-approves by default in
  every batch run.** `AUTONOMY="confirm"` is the declared and defended
  setting (see `docs/D1_AGENT_LOOP.md`), and the gate genuinely does hold
  or pass based on that callback's return value — proven independently by
  `experiments/d3_guardrails/run_guardrail_cases.py`'s
  `autonomy_confirm_refused` case (`approve=lambda: False` → `book_slot`
  never called) and `autonomy_suggest_never_books` (autonomy=suggest
  overrides `approve` entirely). But none of D4, D5(a), D5(b) or D7 pass a
  real `approve` callback to `run_case` — `src/agent.py`'s
  `if approve is None: approve = lambda action, payload: True` stands in
  for an operator so that batch evaluation runs are unattended and
  reproducible. This means every "book" decision in the headline pass
  rates was rubber-stamped by that lambda, not by a simulated human
  reviewing the specific booking — the gate mechanism is proven correct in
  isolation, but not exercised as a real approval step at eval scale.
- **Several real bugs, plus genuine model-behaviour limitations, were
  found and fixed via live testing**, all in `src/` and all documented in
  `STATUS.md`'s multi-round account: infrastructure gaps (the agent never
  told a live model which referral to handle; several
  crash-on-unexpected-shape bugs), a genuinely ambiguous v2 output schema,
  and a systematic skip of the duplicate-appointment check before booking
  that required a **third poka-yoke** at the orchestration layer. A
  **fourth poka-yoke** (verifying a merely-*declared* booking, and
  backfilling an omitted `booked` field from an already-succeeded call)
  plus a call-shape normalisation closed most of the rest. **Final
  numbers, on the current 55-case/95-trial set: v1 41.1% (39/95, negative
  pass 15.0%), v2 100% (95/95)** — see `results/descriptors/comparison.json`'s
  `interpretation` and `docs/D5_MODEL_BATTERY.md`.
- **The judgement queue (LLM-as-judge) shows a real gap below the code
  check.** Code check: 100% (95/95). Judgement check (a different model,
  `anthropic/claude-haiku-4.5`, grading `openai/gpt-4o-mini`'s answers):
  **74.6% (41/55)** — the model reaches the right decision almost every
  time but its `reason` text often omits the specific fact in
  `must_record`. See `docs/D4_EVALUATION_METRICS.md`.
- **Injection detection is intentionally crude** (substring/regex), matching
  the scaffold's own stated design — see `src/tools.py`'s module docstring.
  It is measurably better than doing nothing (19/19 on the D3 checklist,
  including a benign false-positive control and 3 differently-shaped
  hostile-text cases) but is not a robust defence against a determined
  adversary.
- **The scripted "policy" backend is a reference solver, not a language
  model.** Its 100% pass rate on the code check demonstrates the tools,
  guardrails and harness are wired correctly; it says nothing on its own
  about how a real LLM would perform — that is what the live numbers above
  are for.
- **The eval set (55 cases, 35 book / 20 negative, 36.4%) exceeds the
  brief's stated 30–50 case range and 6–10 negative guidance** — both
  deliberate, both explicitly defended in `docs/D4_EVALUATION.md`, since
  the brief states "going above these numbers is allowed and going below
  is not."
