# D6 — Cost to Serve

## Measurement status (read this first)

D5(b)'s live model battery is now complete: **5 models, 107 trials
each, real OpenRouter usage, on the identical 45-case eval set** —
`results/live/model_comparison.json`. The **measured, per-model cost
table below is the headline result of this document**, built entirely
from that real data (`results/cost/d6_measured_all_models.json`).

The **illustrative 80/90/95/99% sweep further down is kept for
reference only** — it shows how the cost arithmetic responds to
success rate in general, using the scripted backend's token *estimate*
(not a real model's usage) as its variable-cost input. It predates the
live battery and is superseded by the measured section for every
purpose except showing the shape of the fallback-cost curve.

## Measured: cost per model (`results/cost/d6_measured_all_models.json`)

All 5 models ran the identical 45-case/107-trial, v2-prompt evaluation
set with real tools, guardrails, and OpenRouter billing. `success_rate`
is the D4 code-check pass rate over those 107 trials.

| Model | Success rate | Negative success | Mean latency | Cost/referral | Monthly cost @ 4,000 referrals |
|---|---|---|---|---|---|
| **GPT-4o Mini** | 100.0% | 100.0% | 6.35s | US$0.0027 | **US$10.80** |
| **Qwen 2.5 72B Instruct** | 99.1% | 98.9% | 14.52s | US$0.0882 | US$352.80 |
| **Gemini 2.5 Flash Lite** | 90.6% | 89.2% | 3.85s | US$0.8601 | US$3,440.40 |
| **Llama 3.1 8B Instruct** | 39.2% | 33.3% | 7.62s | US$5.5720 | US$22,288.00 |
| **Mistral NeMo** | 33.6% | 35.5% | 6.85s | US$6.0851 | US$24,340.40 |

**The single biggest finding in this document:** at 4,000 referrals/month,
the "cheap" small models are the most expensive to actually run. Every
model's raw per-token API price is a few thousandths of a US cent per
referral — utterly negligible next to the fallback cost. What separates
a US$10.80/month system from a US$24,340/month one is **success rate
alone**: below ~90%, the expected fallback term (`(1 - success_rate) ×
US$9.1667`) swamps everything else. Llama-3.1-8B and Mistral-NeMo are
priced at a fraction of GPT-4o-mini per token, yet cost **~2,000×
more per month**, because roughly 2 in 3 of their referrals need a
human to clean up after them. **Choosing the model with the highest
measured success rate is the dominant cost lever in this entire
system** — not prompt length, not token trimming, not turn count.

Qwen 2.5 72B Instruct is the interesting middle case: near-parity
success rate with GPT-4o-mini (99.1% vs 100%) but at ~33× the monthly
cost, driven by its much higher per-call latency (14.5s vs 6.35s) and
correspondingly larger token usage — worth noting as a real trade-off
if GPT-4o-mini itself were ever unavailable, but not a reason to prefer
it over GPT-4o-mini here.

## Reference only: illustrative sweep (superseded by the measured table above)

The tables in this section predate the D5(b) live battery and use the
scripted backend's token **estimate**, not a real model's usage, swept
across an illustrative success-rate range rather than a measured one.
They are kept because they show the shape of the fallback-cost curve
independent of any one model, but every number in them is provisional
— read the measured section above for the real figures.

## Inputs (`results/cost/d6_inputs.json`)

| Input | Value | Source |
|---|---|---|
| Referrals / month | 4,000 | given |
| Fallback rate | US$55/hour | given |
| Fallback time | 10 minutes | given |
| **Fallback cost per failure** | **US$9.1667** | `55/60*10` |
| Variable model cost / referral | US$0.00276 | mean scripted **estimate**, 35 cases |

## Cost by illustrative success rate (`results/cost/d6_model_costs.json`)

| Success rate | Expected fallback / referral | Cost / referral | Cost / successful referral | Monthly cost |
|---|---|---|---|---|
| 80% | US$1.8333 | US$1.8361 | US$2.2951 | US$7,344.40 |
| 90% | US$0.9167 | US$0.9195 | US$1.0217 | US$3,678.00 |
| 95% | US$0.4583 | US$0.4611 | US$0.4854 | US$1,844.40 |
| 99% | US$0.0917 | US$0.0945 | US$0.0955 | US$378.00 |

The variable model cost (fractions of a cent) is negligible next to the
fallback cost (US$9.17) at every success rate tested — the monthly bill is
overwhelmingly a function of **how often a human has to clean up**, not of
how many tokens the agent uses. This is a genuine finding from the
arithmetic, not an assumption: see the cost-levers discussion below.

## Sensitivity: ±10 percentage points around a 90% baseline (`d6_sensitivity.json`)

| Success rate | Δ from baseline | Cost / referral | Monthly cost |
|---|---|---|---|
| 80% | −10pp | US$1.8361 | US$7,344.40 |
| 90% | baseline | US$0.9195 | US$3,678.00 |
| 100% | +10pp | US$0.0028 | US$11.04 |

A 10-point swing in success rate around the illustrative 90% baseline moves
the monthly bill by roughly **US$3,666 to US$7,333**, depending on
direction — an order of magnitude larger than any plausible saving from
trimming tokens. **This is the single clearest argument in this cost model
for prioritising success-rate work (better prompts, better tools, more
guardrails) over token-efficiency work**, at least until success rate is
comfortably above ~99%, past which the fallback term becomes small enough
for token cost to start mattering by comparison.

## Break-even success rate (`d6_breakeven.json`)

Defined as the success rate `s*` at which automating costs the same, per
referral, as paying the manual fallback for every single referral with no
automation at all:

```
variable_cost + (1 - s*) * fallback = fallback
s* = variable_cost_per_referral / fallback_cost_per_failure
   = 0.00276 / 9.1667
   ≈ 0.0301%
```

Using the real per-model variable costs from the measured table above,
the break-even point is essentially unchanged across all 5 models
(0.03%–0.66%) — every model's variable cost is so far below the
US$9.1667 fallback that break-even is never the binding constraint in
practice. The number that actually determines whether a model is worth
running is not "does it clear break-even" (they all clear it trivially)
but **how close its measured success rate gets to 100%** — see the
measured table above, where that gap alone spans US$10.80/month to
US$24,340/month.

## Four required cost-lever experiments

### Experiment 1 — tool block size (larger vs trimmed tool set)

`experiments/d2a_tools/tool_set_comparison.py` — compares the shipped,
trimmed 7-tool set against a larger 9-tool set carrying the two
candidate tools rejected in D2(a) (`get_specialty_info`,
`list_all_specialties`). Result (`results/descriptors/tool_set_comparison.json`):

| Metric | Trimmed (7 tools) | Larger (9 tools) |
|---|---|---|
| Tool block size | 1,776 tokens (est.) | 1,954 tokens (est.) |
| Overhead per turn | — | +178 tokens |
| Wasted tokens over one 45-case pass | 0 | ~24,564 |
| Pass rate | unaffected — both candidate tools are never called by the reference solver on any of the 45 cases | unaffected |

**Removing tool context reduces cost with zero accuracy cost here**,
because both rejected tools are pure overhead: their function is
already covered by `check_referral_criteria`'s pre-computed verdicts.
This is the cleanest possible answer to the experiment's own question
— the two tools were never providing any correctness value to trade
away in the first place.

### Experiment 2 — turn count (sequential vs parallel, reusing D2(c))

See D2(c)'s output table in `docs/D2_TOOL_DESIGN.md` in full;
summarised (`results/parallelism/comparison.json`, `REF-5602`):

| Metric | Sequential | Parallel |
|---|---|---|
| Turns | 6 | 5 |
| Total tokens (est.) | 38,220 | 29,460 |
| Cost (est.) | US$0.00608 | US$0.00472 |
| Pass rate | 100% | 100% |

Grouping the one independent pair (`check_referral_criteria` +
`lookup_patient`) into a single turn saves 16.7% of turns and 22.9% of
tokens on this case, with **zero change to correctness** — parallelism
never trades accuracy for cost here, as required.

### Experiment 3 — observation size (verbose vs compact `get_clinic_slots`)

`experiments/d6_cost/run_observation_size_experiment.py` — a local
monkeypatch (no change to the shipped `src/tools.py`) compares the
verbose observation (`{clinic, specialty, band, date, time,
capacity_remaining}` per row — `specialty`/`band` are already known to
the model as its own call arguments, and `capacity_remaining` is never
used once the tool has already filtered to capacity>0 rows) against a
compact one (`{clinic, date, time}` only, same rows, same order). Live
on `openai/gpt-4o-mini`, the 14 `book` cases that actually see this
observation (`results/cost/d6_observation_size_experiment.json`):

| Metric | Verbose | Compact |
|---|---|---|
| Pass rate | 100.0% (14/14) | 100.0% (14/14) |
| Avg tokens in | 9,134.5 | 9,109.9 |
| Avg tokens out | 274.3 | 269.6 |
| Avg turns | 4.00 | 4.00 |
| Total cost (14 trials) | US$0.021486 | US$0.021397 |

**Token saving: 0.27%** — real but small at this dataset's scale,
because `get_clinic_slots` returns few rows per query here and its
observation is resent for only 1-2 subsequent turns before the run
concludes. The saving would scale with the number of rows returned and
the number of turns remaining after the call — meaningful on a busier
clinic dataset with many slots per query, marginal on this one. Pass
rate is unaffected either way: the three trimmed fields carried no
information the model needed to make its booking decision correctly.

### Experiment 4 — success rate (cheap vs expensive model)

This is the D5(b)/D6 measured-all-models table above, in full: 5 real
models spanning 3 price tiers, none from the same family, same v2
prompt, same eval set, same tools, same guardrails. The cheapest models
by sticker price (`llama-3.1-8b-instruct`, `mistral-nemo`) are the most
expensive to actually run (US$22,288–US$24,340/month) because their
success rate is under 40%; the reference model (`gpt-4o-mini`) is
cheapest overall at US$10.80/month purely because it is nearly always
right. See "Measured: cost per model" above for the full table.

## Which cost lever actually matters most

**Success rate, by a wide margin.** Experiments 1–3 each measure a real
but small effect (tens to low-thousands of tokens per run); Experiment
4 measures a **~2,000× swing in monthly cost** between the best and
worst model, driven entirely by the fallback term. At this problem's
scale (US$9.17/failure vs. fractions of a cent per token), no amount of
prompt or tool trimming can close a gap that success rate alone opens.
The practical order of priority this data supports: pick the
highest-success-rate model first, then trim tool/observation bloat as
a secondary, much smaller optimization once that choice is made.
