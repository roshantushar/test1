# Report Evidence Index

A map from every numeric or factual claim this project can currently support
to the file that backs it, and the command that reproduces it. Use this when
writing the final report so every figure cites its source file and trial
count, per the assignment's "before you submit" checklist.

All D0–D7 deliverables below are **COMPLETE** — see `STATUS.md` for the
full per-stage table. Every number here is real, measured, on-disk
evidence; nothing in this file is illustrative or projected. The
evaluation set was rebalanced twice after its original 69%-negative
design (see `docs/D4_EVALUATION.md`'s "Rebalance history" section) and
now stands at **55 cases: 35 book / 20 negative (36.4%)**, 95 trials
under the D4 trial policy. Every live-model number below is measured
against this final, current set.

| Claim | Evidence file | Reproduce with |
|---|---|---|
| Scaffold left fully unmodified | `docs/D0…D7` cite scaffold files by path; verification diff run during authoring (see README "Relationship to the scaffold") | `diff -rq "A2_scaffold 2" <clone>/A2_scaffold\ 2` |
| All 15 shipped rows preserved exactly | verified byte-for-byte during authoring | see README §"Validating the data" |
| 55-case evaluation set, 20 negative (36.4%) / 35 positive (63.6%) | `data/expected_outcomes_B.json` | `python3 data/check_my_data_final.py` |
| Data hangs together, 0 warnings | (validator output) | `python3 data/check_my_data_final.py` |
| Scripted backend: 95/95 trials pass (100%), median 2 turns, worst 5 | `results/scripted/final_eval.json` | `python3 src/run_eval.py` |
| Three regression anchors (REF-5602 book, REF-5614 request_information, REF-5590 escalate) | `results/scripted/final_eval.json` (per-case) | `python3 src/run_eval.py REF-5602` (etc.) |
| D2(c): parallel saves 16.7% of turns on REF-5602, 0 wasted calls | `results/parallelism/comparison.json` | `python3 experiments/d2c_parallelism/run_comparison.py` |
| D3(b): 19/19 guardrail cases pass (100%), incl. 4 hostile-text + 1 benign control (all running the real agent loop end to end, not the detector in isolation), and the required "monthly limit per user" cap (guardrail #7) | `results/guardrails/guardrail_results.json` | `python3 experiments/d3_guardrails/run_guardrail_cases.py` |
| D7 failure 1 (loop): reproduced, restored, matches "before" (1.63x cost multiplier) | `results/d7/failure_1_loop.json` | `python3 experiments/d7_failures/failure_1_loop.py` |
| D7 failure 2 (interface): unsafe booking reproduced and fixed | `results/d7/failure_2_slot_interface.json` | `python3 experiments/d7_failures/failure_2_slot_interface.py` |

## D0 — reliability, live-measured

| Claim | Evidence file | Reproduce with |
|---|---|---|
| v2: P=1.0000 (95/95), T=4 median → s=1.0000 per step | `experiments/d0/reliability_calc.json` (`live_one_model` block) | `python3 experiments/d0/reliability_calc.py` |
| v1: P=0.4105 (39/95), T=4 median (tied with v2) → s=0.8005 per step | same file | same script |
| The bigger problem is low per-step reliability, not too few turns: v1 and v2 need the SAME median turn count, yet v1's P is less than half of v2's — the gap is entirely within-turn, not turn-count | `docs/D0_AGENT_JUSTIFICATION.md` §9 | — |

## D5 — v1 vs v2 prompt/descriptor comparison (whole-prompt, one model), live-measured

`openai/gpt-4o-mini`, 95 trials/version, identical eval set, tools,
guardrails, autonomy — only the system prompt (rules + answer schema +
every tool descriptor) differs.

| Claim | Evidence file | Reproduce with (needs `OPENROUTER_API_KEY`, `A2_BACKEND=live`) |
|---|---|---|
| v1 41.1% (39/95) vs v2 100.0% (95/95); negative-case pass rate v1 15.0% (9/60) vs v2 100.0% (60/60) | `results/descriptors/{v1_live,v2_live,comparison}.json` | `python3 experiments/d2b_descriptors/run_live_comparison.py` |
| v1's failures are almost entirely a labelling/schema gap (correct decision, wrong or missing exact trigger/missing-string), not a reasoning gap — a visible minority are genuine decision errors (booking a red-flag or injected referral) | `results/descriptors/v1_live.json` (`failures` field), `comparison.json`'s `interpretation` | same script, v1 arm |

## D2(b) — REQUIRED single-tool ablation (`get_clinic_slots`), live-measured

`openai/gpt-4o-mini`, 41 trials/version (35 book cases + 2
`no_slot_in_window` escalate cases × 3 trials), every other v2 prompt
component held fixed — only this one tool's own descriptor varies.

| Claim | Evidence file | Reproduce with |
|---|---|---|
| v1-weak descriptor 100% (41/41) vs v2-full descriptor 100% (41/41) — a genuine null result on correctness | `results/descriptors/single_tool_ablation_get_clinic_slots.json` | `python3 experiments/d2b_descriptors/run_single_tool_ablation.py` |
| v2's fuller descriptor costs 4.4% more input tokens (9,127 vs 8,746 avg) for zero pass-rate gain on this model — descriptor completeness and prompt-level ordering rules are not interchangeable | same file | — |

## D5(b) — 5-model family comparison, live-measured

All 5 models ran the identical v2 prompt, tool set, guardrails,
autonomy setting, and 55-case/95-trial eval set.

| Claim | Evidence file | Reproduce with |
|---|---|---|
| gpt-4o-mini 100.0% (95/95), gemini-2.5-flash-lite 95.8% (91/95), qwen-2.5-72b-instruct 83.2% (79/95), llama-3.1-8b-instruct 52.6% (50/95), mistral-nemo 21.1% (20/95) | `results/live/model_comparison.json`, one JSON file per model in `results/live/` | `python3 experiments/d5_models/run_live_battery.py` |
| Full metric breakdown (negative pass rate, median turns, latency, tokens, cost) per model | `docs/D5_MODEL_BATTERY.md` | same script |
| Qwen's score dropped from 99.1% (measured on an earlier, less-varied 45-case set) to 83.2% on the final, more-varied 55-case set — a genuine, re-verified result, not a fluke, driven by both accuracy and a 25.6s mean latency (highest in the battery) | `results/live/qwen_qwen-2.5-72b-instruct.json`, `docs/D5_MODEL_BATTERY.md` | same script |
| `anthropic/claude-3-haiku` scores 0% (measured on the earlier 45-case set, not re-run since) — a genuine protocol-compliance failure (dumps its whole plan as concatenated JSON objects instead of one move per turn), verified via direct API testing, not a harness bug — excluded from the headline table per explicit request but kept as raw data | `results/live/anthropic_claude-3-haiku.json`, `docs/D5_MODEL_BATTERY.md` | — |
| `google/gemini-flash-1.5` does not exist on this OpenRouter account's catalog; substituted with `google/gemini-2.5-flash-lite` | `docs/D5_MODEL_BATTERY.md` | `curl https://openrouter.ai/api/v1/models` |
| 9 live-testing robustness bugs found and fixed across both rebalances (incomplete `book_slot` args, non-dict `booked` shape at 2 separate call sites, `ValueError` from tool validation, a top-level JSON array response, an extra unexpected `book_slot` kwarg, and 4 HTTP-transport retry gaps incl. 5xx handling and provider inline-error retries) | `docs/D5_MODEL_BATTERY.md` hardening section | — |

## D4 — evaluation checks and judgement, live-measured

| Claim | Evidence file | Reproduce with |
|---|---|---|
| Code check: 100% (95/95 trials), zero off-diagonal decision confusion | `results/evaluation/eval_set_summary.json` | `python3 experiments/d4_evaluation/compute_metrics.py --source live` |
| LLM-as-judge (`anthropic/claude-haiku-4.5`): 74.6% (41/55 cases) — 14 failures, all the same pattern: a bare-outcome `reason` that omits the specific fact (red-flag phrase, mismatch justification, slot detail) the answer key's `must_record` requires, across both `book` and `escalate` decisions | `results/evaluation/judge_results_live.json` | `python3 experiments/d4_evaluation/compute_metrics.py --source live --judge` (needs `OPENROUTER_API_KEY`) |

## D6 — cost to serve, live-measured across all 5 models

| Claim | Evidence file | Reproduce with |
|---|---|---|
| Three-layer model fully built: Layer 1 (measured tokens×price), Layer 2 ((1−success)×US$9.1667), **Layer 3 (US$25/month fixed, stated with assumptions — compute/storage/eval-runs/monitoring)** | `experiments/d6_cost/run_cost_model.py` (`LAYER_3_FIXED_MONTHLY_USD`) | `python3 experiments/d6_cost/run_cost_model.py` |
| Monthly cost @ 4,000 referrals (incl. Layer 3) spans US$33.40 (gpt-4o-mini, 100% success) to US$28,979.40 (mistral-nemo, 21.1% success) — driven by success rate via the fallback term, not per-token price | `results/cost/d6_measured_all_models.json` | same script (reads `results/live/model_comparison.json`) |
| **Switch break-even** (the correct question — how good a cheaper model needs to be before switching pays off, not "automate vs. no automation"): `mistral-nemo` (cheapest raw token price) would need **99.99%** success to be worth switching to from `gpt-4o-mini` (already cheapest AND 100% accurate) — measured at 21.1%, nowhere close | `results/cost/d6_switch_breakeven.json` | same script |
| Real per-model sensitivity, ±10pp around each model's OWN measured rate (not an illustrative baseline): the cost ranking survives the whole range for every model; swing is ~US$7,333 uniformly once a model is below ~95% (`0.20 × US$9.1667 × 4,000` — the arithmetic, not a model-specific detail) | `results/cost/d6_real_sensitivity.json` | same script |
| Which cost lever dominated, measured: tool block size (Experiment 1, linear in turns) dominated observation size (Experiment 3, compounds) by ~36× at this dataset's scale (38,982 vs 1,085 tokens) — a dataset-scale-dependent finding, not a general rule | `docs/D6_COST_MODEL.md` | `python3 experiments/d2a_tools/tool_set_comparison.py`, `python3 experiments/d6_cost/run_observation_size_experiment.py` |
| Experiment 3 (observation size, verbose vs compact `get_clinic_slots`): 100%/100% pass, 0.34% token saving on 35 book-case trials | `results/cost/d6_observation_size_experiment.json` | `python3 experiments/d6_cost/run_observation_size_experiment.py` |
| A hardcoded `N_REFERRALS_IN_EVAL_SET=45` constant was silently overstating cost-per-referral by ~22% after the case-count rebalance; fixed to read the count dynamically from the answer key | `experiments/d6_cost/run_cost_model.py` | — |
| No reasoning model used (mean output tokens 210–477 across all 5 models, no order-of-magnitude spike) and no prompt caching used — the baseline is deliberately the plain one, nothing cleverer folded in | `docs/D6_COST_MODEL.md` | — |
| Illustrative 80/90/95/99% sweep and the original automate-vs-no-automation break-even (both superseded, kept for reference only) | `results/cost/d6_model_costs.json`, `d6_sensitivity.json`, `d6_breakeven.json` | same script |

## Notes on numbers that changed during authoring

- The evaluation set was rebalanced **twice** after its original
  69%-negative design: first to 35 book / 10 negative (45 total, per
  "36 ordinary / 9 negative" direction — 9 was mathematically
  impossible given the fixed shipped 15's own 10 negatives, so 10 was
  the agreed floor), then +10 more negative cases (block 7,
  `REF-6071`–`6080`) back on top, reaching the current, final **55
  cases: 35 book / 20 negative**. See `docs/D4_EVALUATION.md`'s
  "Rebalance history" section for the full account. Every number in
  this file is measured against the final 55-case set except where a
  row explicitly says otherwise (Claude 3 Haiku).
- v2's D2(b)/D5(b) pass rate on the 45-case (pre-second-rebalance) set
  was first measured at 98.1% (105/107), then 100% (107/107) after a
  re-run undertaken for an unrelated D4 evidence-recording fix. Both
  numbers are superseded by the current 55-case, 100% (95/95) result.
- D6's cost figure was first reported as US$696.40/month from a single
  model at an interim pass rate, then US$10.80/month for gpt-4o-mini
  on the 45-case set. It is now US$8.40/month on the final 55-case set,
  alongside the other 4 models' current figures in the table above.
