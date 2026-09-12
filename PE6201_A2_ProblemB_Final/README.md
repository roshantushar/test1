# PE6201 A2 — Problem B (Final): Outpatient Referral Coordination

A bounded, tool-using ReAct agent that reads one outpatient referral at a
time and returns exactly one of `book` / `request_information` / `escalate`,
gating the one irreversible action (`book_slot`) behind an autonomy check.
Built from scratch in this folder after studying the official read-only
scaffold at `../A2_scaffold 2/` — see "Relationship to the scaffold" below.

## Project layout

```
PE6201_A2_ProblemB_Final/
├── src/                 config, tools, backends, agent, guardrails,
│                        harness, prompt, run_eval, demo_loop_failure
├── data/                the EXTENDED, project-owned fixture generator,
│                        checker, and answer key (45 cases, negative-heavy
│                        by explicit user direction - see docs/D4)
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
currently reports **zero warnings, zero failures** over 45 referrals, 8
specialties (5 shipped + `NEURO`, `RESP` and `ENDO`, new), 29 clinic slots,
37 patients.

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
**Current result: 107/107 trials passed (100%)**, median 2 turns, worst
case 5, zero step-cap hits.

## Live backend setup (D2b, D5b)

A live OpenRouter run against `openai/gpt-4o-mini` has been completed for
both D2(b) (v1 vs v2: **27.1% vs 98.1%**, all 107 trials of the current,
negative-heavy set) and D5(b) (v2 alone: 98.1%) — see
`results/descriptors/`, `results/live/`, and `STATUS.md` for the full
account of what was found and fixed along the way. The multi-model family
comparison D5(b) also asks for has not been run yet. To reproduce or
extend either:

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
| D2(b) live (not yet run) | `python3 experiments/d2b_descriptors/run_live_comparison.py` | `results/descriptors/*.json` |
| D5(b) live (not yet run) | `python3 experiments/d5_models/run_live_battery.py` | `results/live/*.json` |

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

- **Live coverage is one model, not the full D5(b) battery.** A live
  OpenRouter run against `openai/gpt-4o-mini` was used for both D2(b) (v1
  vs v2: **27.1% vs 98.1%**, all 107 trials of the current, 69%-negative
  set, real measured usage) and D5(b) (v2 alone: 98.1%) — see
  `results/descriptors/`, `results/live/`, and `STATUS.md` for the full
  account. D5(b)'s multi-model family comparison has not been run yet.
- **Several real bugs, plus genuine model-behaviour limitations, were
  found and fixed via this live testing**, all in `src/` and all
  documented in `STATUS.md`'s multi-round account: infrastructure gaps
  (the agent never told a live model which referral to handle; several
  crash-on-unexpected-shape bugs), a genuinely ambiguous v2 output schema
  (fixing it raised v2's pass rate from 5.5% to 47.3% on an earlier
  version of the set), and a systematic skip of the duplicate-appointment
  check before booking that required a **third poka-yoke** at the
  orchestration layer. A **fourth poka-yoke** (verifying a
  merely-*declared* booking, and backfilling an omitted `booked` field
  from an already-succeeded call) plus a call-shape normalisation closed
  most of the rest. v1 was then rebuilt to genuinely vary all three prompt
  components (rules, answer format, descriptors). **Final numbers, on the
  current, redesigned, negative-heavy 45-case/107-trial set: v1 27.1%
  (29/107), v2 98.1% (105/107)** — a much larger gap than an earlier,
  mostly-positive version of the set showed (45.5% vs 100%), because this
  set is dominated by cases needing an exact trigger/missing label, which
  v1's schema cannot supply even when it reaches the right underlying
  decision — see `results/descriptors/comparison.json`'s `interpretation`.
  v2's 2 residual failures were confirmed non-reproducible (live-model
  stochasticity, not a systematic gap).
- **The judgement queue is not yet worked through by a human.**
  `results/scripted/final_eval.json`'s `judgement_queue` field is populated
  (one item per case, with its `must_record` list) but no verdict has been
  entered — see `STATUS.md` for this as a remaining task.
- **Injection detection is intentionally crude** (substring/regex), matching
  the scaffold's own stated design — see `src/tools.py`'s module docstring.
  It is measurably better than doing nothing (13/13 on the D3 checklist,
  including a benign false-positive control) but is not a robust defence
  against a determined adversary.
- **The scripted "policy" backend is a reference solver, not a language
  model.** Its 100% pass rate on the code check demonstrates the tools,
  guardrails and harness are wired correctly; it says nothing on its own
  about how a real LLM would perform — that is what the live numbers above
  are for.
- **The eval set is deliberately negative-heavy (69%), at the user's
  explicit direction** — 6 blocks of 5 cases each, versus the assignment's
  suggested 6–10 negative overall (see `docs/D4_EVALUATION.md`'s
  "deliberate deviation" section). Headline pass rates on this set should
  be read as performance on a negative-heavy stress test, not as
  representative of a real referral mix.
