# Contributions

Names below are placeholders — **[Member N — Name]** — replace each with
the real team member's name before committing. The split follows the
brief's own structure (D0–D7, plus D5(b)'s one-live-model-per-member
rule) so that the commit history can corroborate this file, per section 8
of the brief.

## [Member 1 — Name] — D0, the agent loop, and repo integration

- `docs/D0_AGENT_JUSTIFICATION.md`, `experiments/d0/reliability_calc.py`, `experiments/d0/reliability_calc.json`
- `src/agent.py`, `src/decision_log.py`, `src/config.py`, `src/prompt.py`
- `docs/D1_AGENT_LOOP.md`
- `README.md`, `STATUS.md`, `requirements.txt`, `docs/REPORT_EVIDENCE.md`

## [Member 2 — Name] — D2, the tool layer

- `src/tools.py`
- `experiments/d2a_tools/`, `experiments/d2b_descriptors/`, `experiments/d2c_parallelism/`
- `docs/D2_TOOL_DESIGN.md`
- `results/descriptors/`, `results/parallelism/`

## [Member 3 — Name] — D3, the guardrail layer

- `src/guardrails.py`
- `experiments/d3_guardrails/`
- `docs/D3_GUARDRAILS.md`
- `results/guardrails/`

## [Member 4 — Name] — D4, the evaluation set and harness

- `data/make_fixtures_B_final.py`, `data/check_my_data_final.py`, `data/expected_outcomes_B.json`, `data/generated/`
- `src/harness.py`, `src/judge.py`, `src/run_eval.py`
- `experiments/d4_evaluation/`
- `docs/D4_EVALUATION.md`, `docs/D4_EVALUATION_METRICS.md`
- `results/evaluation/`, `results/scripted/`

## [Member 5 — Name] — D6, the cost-to-serve model

- `experiments/d6_cost/`
- `docs/D6_COST_MODEL.md`
- `results/cost/`

## [Member 6 — Name] — D7, the two reproduced failures

- `src/demo_loop_failure.py`, `src/backends.py`
- `experiments/d7_failures/`
- `docs/D7_FAILURES.md`
- `results/d7/`

## D5(b) — the live model battery (one member, one model, own key)

Per the brief: every member runs one live battery on their own
OpenRouter key, regardless of which build section they own above.

| Member | Model | Result file |
|---|---|---|
| [Member 1 — Name] | `openai/gpt-4o-mini` | `results/live/openai_gpt-4o-mini.json` |
| [Member 2 — Name] | `google/gemini-2.5-flash-lite` | `results/live/google_gemini-2.5-flash-lite.json` |
| [Member 3 — Name] | `qwen/qwen-2.5-72b-instruct` | `results/live/qwen_qwen-2.5-72b-instruct.json` |
| [Member 4 — Name] | `meta-llama/llama-3.1-8b-instruct` | `results/live/meta-llama_llama-3.1-8b-instruct.json` |
| [Member 5 — Name] | `mistralai/mistral-nemo` | `results/live/mistralai_mistral-nemo.json` |
| [Member 6 — Name] | D2(b)'s v1 pass, on `openai/gpt-4o-mini` | `results/descriptors/v1_live.json`, `results/descriptors/v2_live.json`, `results/descriptors/comparison.json` |

`results/live/model_comparison.json` and
`docs/D5_MODEL_BATTERY.md` bring the battery together and are shared
work — see [Member 1 — Name]'s section above.

## Shared / integration work

- `notebooks/PE6201_A2_ProblemB_Experiments.ipynb` — [Member — Name]
- Final merge, cross-checking every deliverable against the brief, and
  fixing gaps found in review — [Member — Name]

## Contribution statement

All members are contributing. *(Or, if not true: name the member, what
was agreed, and what has happened instead — see section 8 of the brief.
Silence here is read as "all members are contributing.")*
