# Contributions

Matches the "Who owns what" table from `TEAM_DECLARATION` exactly (strand →
feeds → owner). Two things aren't explicit in that table and are assumed
here — flagged where they occur, adjust if your team divided them
differently. Everyone commits their own section themselves so the commit
history actually corroborates this file, per section 8 of the brief.

## Syedyaseen Roshan Tushar & Shen Shuo — the loop and the tools (D1, D2(a), D2(c))

- `src/agent.py`, `src/decision_log.py` (D1)
- `docs/D1_AGENT_LOOP.md`
- `src/tools.py`, `experiments/d2a_tools/tool_set_comparison.py` (D2(a))
- `experiments/d2c_parallelism/run_comparison.py`, `experiments/d2c_parallelism/plot_token_growth.py` (D2(c))
- `results/descriptors/tool_set_comparison.json`, `results/parallelism/`, `results/live/token_growth_all_models.png`, `results/live/token_growth_fits.json`
- `docs/D2_TOOL_DESIGN.md` — **shared with Gong Xinyi**: this one file covers D2(a)/D2(c) (this pair) and D2(b) (Gong Xinyi) together. Whoever commits it should say in the commit message which sections they wrote, or split it into two docs if you'd rather the history read cleanly per-author.
- `docs/D0_AGENT_JUSTIFICATION.md`, `experiments/d0/reliability_calc.py`, `experiments/d0/reliability_calc.json` — **not in the table's strand list; assumed here** since D0 precedes and sets up D1. Move it if your team assigned it elsewhere.
- `docs/D7_FAILURES.md`, `src/demo_loop_failure.py`, `src/backends.py`, `experiments/d7_failures/` — **also not in the table; assumed here** since both reproduced failures extend this pair's own loop/tool-interface work. Move it if assigned elsewhere.
- `src/config.py`, `src/prompt.py` — shared infrastructure the loop depends on.

## Gong Xinyi — descriptors, the v1-to-v2 rewrite, guardrail layer (D2(b), D3)

- `experiments/d2b_descriptors/run_live_comparison.py`, `experiments/d2b_descriptors/run_single_tool_ablation.py`
- `results/descriptors/comparison.json`, `results/descriptors/single_tool_ablation_get_clinic_slots.json`, `results/descriptors/v1_live.json`\*, `results/descriptors/v2_live.json`\*, `results/descriptors/v1_vs_v2_cost_tokens.png`
- `src/guardrails.py`
- `experiments/d3_guardrails/run_guardrail_cases.py`
- `docs/D3_GUARDRAILS.md`
- `results/guardrails/guardrail_results.json`
- D2(b) section of `docs/D2_TOOL_DESIGN.md` — see the shared-file note above.

\* `results/descriptors/v1_live.json`/`v2_live.json` are the whole-prompt v1-vs-v2 comparison (this strand's own experiment) — not to be confused with Zhong Yingmei's separate D5(b) v1-pass battery below, which reuses the same descriptor work on the full eval set.

## Liu Xinyao — evaluation harness and the scripted run (D4, D5(a))

- `src/harness.py`, `src/judge.py`, `src/run_eval.py`
- `data/make_fixtures_B_final.py`, `data/check_my_data_final.py`, `data/expected_outcomes_B.json`, `data/generated/`
- `experiments/d4_evaluation/compute_metrics.py`
- `docs/D4_EVALUATION.md`, `docs/D4_EVALUATION_METRICS.md`
- `results/evaluation/`, `results/scripted/final_eval.json`, `results/decision_log.jsonl`

## Xie Yulong — cost model, ledger, sensitivity (D6)

- `experiments/d6_cost/run_cost_model.py`, `experiments/d6_cost/run_observation_size_experiment.py`
- `docs/D6_COST_MODEL.md`
- `results/cost/`

## All members — evaluation cases (D4), 5–8 each

The 55 cases in `data/expected_outcomes_B.json` and their matching
referrals in `data/generated/data_B/referrals.json` were written across
the whole team. **Caveat, stated plainly:** both are single shared JSON
files — git can't attribute individual case authorship inside one file
after the fact the way it can for separate files owned by one person.
If this needs to show up in the commit history rather than just this
note, the cleanest fix is for each member to commit their own 9–10
cases as a separate, named commit before the file is merged (e.g.
`git commit -m "D4: 9 evaluation cases — Gong Xinyi"`), rather than one
person committing the whole file at the end.

## Live model battery — everyone, one model each (D5(b))

| Member | Model (as declared) | Result file | Note |
|---|---|---|---|
| Syedyaseen Roshan Tushar | `openai/gpt-4o-mini` | `results/live/openai_gpt-4o-mini.json` | |
| Shen Shuo | `anthropic/claude-3-haiku` | `results/live/anthropic_claude-3-haiku.json` | Genuine 0% result — a real protocol-compliance failure (never follows the turn-by-turn format), not a harness bug. Kept as raw data, excluded from the headline D5(b) table — see `docs/D5_MODEL_BATTERY.md`. |
| Gong Xinyi | `google/gemini-1.5-flash` | `results/live/google_gemini-2.5-flash-lite.json` | **Substituted**: `gemini-1.5-flash` does not exist on this OpenRouter account's catalog (verified via `/v1/models`). Ran the closest same-tier equivalent, `gemini-2.5-flash-lite`, instead — say this substitution and why in the report. |
| Liu Xinyao | `meta-llama/llama-3.1-8b-instruct` | `results/live/meta-llama_llama-3.1-8b-instruct.json` | |
| Xie Yulong | `mistralai/mistral-nemo` | `results/live/mistralai_mistral-nemo.json` | |
| Zhong Yingmei | v1 pass on `openai/gpt-4o-mini` | `results/descriptors/v1_live.json`, `results/descriptors/v2_live.json`, `results/descriptors/comparison.json` | This is D2(b)'s required v1-vs-v2 comparison, held to gpt-4o-mini only — not a 6th independent model. |

**Extra, unassigned:** `results/live/qwen_qwen-2.5-72b-instruct.json` (`qwen/qwen-2.5-72b-instruct`) is a 6th live model in the repo beyond the 5 declared above. It isn't anyone's assignment in `TEAM_DECLARATION` — decide as a team whether to keep it (credit it to whoever actually ran it) or drop it from the headline comparison to keep the battery matching the declared table exactly.

`results/live/model_comparison.json` (assembles all models) and
`docs/D5_MODEL_BATTERY.md` — see Zhong Yingmei's section below (report/demo assembly).

## Zhong Yingmei — report and demo assembly

- `docs/D5_MODEL_BATTERY.md`, `results/live/model_comparison.json`, `experiments/d5_models/run_live_battery.py` (assembling the whole battery above)
- `README.md`, `STATUS.md`, `docs/REPORT_EVIDENCE.md`
- `notebooks/PE6201_A2_ProblemB_Experiments.ipynb`
- The team report (sections 4 and 5) and the demo recording — not files in this repo, produced separately per the brief's submission requirements.

## Repo scaffolding (unassigned in the table — commit with whichever section you push first)

`.gitignore`, `requirements.txt`, `CONTRIBUTIONS.md` itself.

## Contribution statement

All members are contributing.
