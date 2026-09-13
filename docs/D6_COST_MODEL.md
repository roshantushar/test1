# D6 — Cost to Serve

## Measurement status (read this first)

D5(b)'s live model battery is now complete: **5 models, 95 trials
each, real OpenRouter usage, on the identical 55-case eval set** —
`results/live/model_comparison.json`. The **measured, per-model cost
table below is the headline result of this document**, built entirely
from that real data (`results/cost/d6_measured_all_models.json`).

The **illustrative 80/90/95/99% sweep further down is kept for
reference only** — it shows how the cost arithmetic responds to
success rate in general, using the scripted backend's token *estimate*
(not a real model's usage) as its variable-cost input. It predates the
live battery and is superseded by the measured section for every
purpose except showing the shape of the fallback-cost curve.

## The three-layer model, and what each layer is priced from

Per the assignment's own Class 5 model:

```
input tokens  ≈ B×T + D×T(T−1)/2       B=base prefix, D=growth/turn, T=turns
layer 1 (variable)  = input×price_in + output×price_out + retrieval/tool fees
layer 2 (fallback)  = (1 − success_rate) × failure_cost
cost per successful task = layer 1 + layer 2
monthly = cost per successful task × volume + layer 3
```

- **Layer 1 (variable):** measured, not estimated — real OpenRouter
  `usage` tokens × each model's real list price, from D5(b)'s live
  battery. No retrieval or tool fees apply (every tool in this project
  reads local fixture data, D0 §1/§6).
- **Layer 2 (fallback):** priced from labour, not a guess — Problem B's
  default role and handling time (Appendix A): US$55/hour × 10 minutes
  = **US$9.1667/failure**.
- **Layer 3 (fixed monthly):** **US$25/month**, stated with its
  assumptions (light always-on compute ~$15, log/decision-record
  storage ~$2, scheduled scripted-eval regression runs ~$3, basic
  monitoring/alerting ~$5) rather than omitted — this project has no
  database beyond local JSON fixtures and one append-only decision
  log (`src/decision_log.py`), so infrastructure needs are minimal at
  this scale; a real deployment would revise this from actual
  infrastructure quotes, not this estimate.
- **No caching, no reasoning model, deliberately.** None of the 5
  models in D5(b) are reasoning models — `mean tokens_out` across all
  5 sits in the 210–477 range with no order-of-magnitude spike (the
  signature of hidden thinking tokens the assignment warns about), so
  no reasoning-token adjustment applies. Prompt caching was not used
  (`backends.py`'s `_live_call` sends no cache-control headers) —
  per the assignment's own guidance ("don't [use a reasoning model] ...
  the marks are in the harness"), this project's baseline is
  deliberately the plain one, with nothing cleverer folded in.
- **Which world this system is in, and why:** this project prices
  layer 2 as `(1 − success_rate) × failure_cost` — **escalate on
  failure**, not `÷ success_rate` (retry until it works). A wrong
  outcome in Problem B goes to a human triage nurse, never back into
  the agent loop for another attempt (D0 §6, §7's "at most once, and
  only after the facts are established" good-run statement) — this
  project is in the escalate world, not the retry world.

## Measured: cost per model (`results/cost/d6_measured_all_models.json`)

All 5 models ran the identical 55-case/95-trial, v2-prompt evaluation
set with real tools, guardrails, and OpenRouter billing. `success_rate`
is the D4 code-check pass rate over those 95 trials. Monthly figures
include Layer 3 (US$25/month, added once, not per referral):

| Model | Success rate | Negative success | Mean latency | Cost/referral (L1+L2) | Monthly cost @ 4,000 referrals (+L3) |
|---|---|---|---|---|---|
| **GPT-4o Mini** | 100.0% | 100.0% | 9.12s | US$0.0021 | **US$33.40** |
| **Gemini 2.5 Flash Lite** | 95.8% | 100.0% | 4.66s | US$0.3885 | US$1,579.00 |
| **Qwen 2.5 72B Instruct** | 83.2% | 91.7% | 25.59s | US$1.5460 | US$6,209.00 |
| **Llama 3.1 8B Instruct** | 52.6% | 33.3% | 8.57s | US$4.3448 | US$17,404.20 |
| **Mistral NeMo** | 21.1% | 25.0% | 15.53s | US$7.2386 | US$28,979.40 |

**The single biggest finding in this document:** at 4,000 referrals/month,
the "cheap" small models are the most expensive to actually run. Every
model's raw per-token API price is a few thousandths of a US cent per
referral — utterly negligible next to the fallback cost (and, at this
volume, next to Layer 3's flat US$25/month too). What separates
a US$33.40/month system from a US$28,979/month one is **success rate
alone**: below ~90%, the expected fallback term (`(1 - success_rate) ×
US$9.1667`) swamps everything else. Llama-3.1-8B and Mistral-NeMo are
priced at a fraction of GPT-4o-mini per token, yet cost **~520–870×
more per month**, because roughly half to three-quarters of their
referrals need a human to clean up after them. **Choosing the model
with the highest measured success rate is the dominant cost lever in
this entire system** — not prompt length, not token trimming, not turn
count.

Gemini 2.5 Flash Lite is the standout budget-tier choice here: 95.8%
overall / **100% negative** success (never missed a safety-critical
case) at the fastest mean latency in the battery (4.66s) and a monthly
cost roughly 185x GPT-4o-mini's but still two orders of magnitude
cheaper than the weaker models. Qwen 2.5 72B Instruct sits in the
middle at 83.2% — a real, measured drop from its 99.1% score on an
earlier, less-varied version of this eval set (see
`docs/D5_MODEL_BATTERY.md`). Its monthly cost is driven by that lower
success rate feeding layer 2, not by latency — latency does not enter
this project's cost formula. Separately, Qwen also carries by far the
highest per-call latency in the battery (25.6s), a genuine operational
drawback if it were ever chosen over GPT-4o-mini, but a causally
distinct one from its token spend and its dollar cost.

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

## Sensitivity, on REAL per-model measured data (`results/cost/d6_real_sensitivity.json`)

Each model's own measured success rate, ±10 percentage points (clamped
to [0,1] — `gpt-4o-mini`'s +10pp point clamps to its already-perfect
100%). Monthly cost includes Layer 3:

| Model | Measured | −10pp | Baseline | +10pp | Swing over 20pp |
|---|---|---|---|---|---|
| gpt-4o-mini | 100.0% | $3,700.20 | $33.40 | $33.40 (clamped) | $3,666.80 |
| gemini-2.5-flash-lite | 95.8% | $5,245.80 | $1,579.00 | $35.40 | $5,210.40 |
| qwen-2.5-72b-instruct | 83.2% | $9,875.40 | $6,209.00 | $2,542.20 | $7,333.20 |
| llama-3.1-8b-instruct | 52.6% | $21,070.60 | $17,404.20 | $13,737.40 | $7,333.20 |
| mistral-nemo | 21.1% | $32,646.20 | $28,979.40 | $25,312.60 | $7,333.60 |

**The conclusion survives the whole range, for every model.** No 20-point
swing changes the RANKING of any model relative to the others — the
worst model at its +10pp best ($25,312.60) is still far more expensive
than the best model at its −10pp worst ($3,700.20). The swing itself is
strikingly uniform once a model is below ~95% (≈$7,333 regardless of
which model), because at that point the fallback term so thoroughly
dominates layer 1 that the swing is set almost entirely by
`0.20 × US$9.1667 × 4,000` — the arithmetic, not any model-specific
detail. Only `gpt-4o-mini` (already at the 100% ceiling) and
`gemini-2.5-flash-lite` (close to it) show a smaller, asymmetric swing,
because their upside is clamped by having little room left to improve.

## Reference only: illustrative sweep, superseded by the real per-model sensitivity above

The table below predates D5(b)'s live battery and sweeps success rate
across an illustrative range using the scripted backend's token
*estimate*, not any real model's measured data. Kept for reference only
— read the section above for the real numbers.

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

## Supplementary automation-vs-manual break-even (`d6_breakeven.json`) — NOT the required A2 break-even

This section answers a different, narrower question than the one A2
requires — kept as a supplementary result, not a substitute for "The
switch break-even" below, which is the assignment's actual required
figure. Defined as the success rate `s*` at which automating costs the
same, per referral, as paying the manual fallback for every single
referral with no automation at all:

```
variable_cost + (1 - s*) * fallback = fallback
s* = variable_cost_per_referral / fallback_cost_per_failure
   = 0.00276 / 9.1667
   ≈ 0.0301%
```

Using the real per-model variable costs from the measured table above,
the break-even point is essentially unchanged across all 5 models
(0.016%–0.028%) — every model's variable cost is so far below the
US$9.1667 fallback that break-even is never the binding constraint in
practice. The number that actually determines whether a model is worth
running is not "does it clear break-even" (they all clear it trivially)
but **how close its measured success rate gets to 100%** — see the
measured table above, where that gap alone spans US$33.40/month to
US$28,979/month.

## The switch break-even — the question that actually decides which model ships

The break-even above answers "does automating beat pure-manual handling
for one model in isolation" — a different, narrower question from the
one that actually decides a shipping choice: **how good would a
CHEAPER model have to be before switching to it stops paying for
itself?** Three quantities, all already measured in D5(b):

```
C = one run on the cheap model, TOKENS ONLY (its own failures are the unknown - they cannot be priced in)
E = one SUCCESSFUL task on the expensive/reference model (its own layer 1 + layer 2, since its rate IS measured)
F = one failure's cost (US$9.1667)

failures affordable = (E − C) / F
breakeven success rate = 1 − failures affordable
```

Applied to this project's own measured data (`results/cost/d6_switch_breakeven.json`)
— **E = `openai/gpt-4o-mini`** (the best-performing model measured, 100%
success, so its own layer 2 is effectively zero), **C =
`mistralai/mistral-nemo`** (the cheapest raw per-token price in the
battery, the natural "cheaper alternative" a team would actually be
tempted by):

| Quantity | Value |
|---|---|
| E — gpt-4o-mini, cost per successful task | US$0.002100 |
| C — mistral-nemo, cost per run (tokens only) | US$0.001480 |
| F — cost of one failure | US$9.1667 |
| E − C (saved per task by switching) | US$0.000620 |
| Failures affordable | 0.0068% |
| **Break-even success rate mistral-nemo would need** | **99.99%** |
| mistral-nemo's actual measured success rate | 21.1% |
| **Clears break-even?** | **No — not remotely close** |

**Read what this means, because it is the point of the exercise.**
`gpt-4o-mini` is *already* both the cheapest model measured AND the
most accurate — there is essentially no per-token saving left on the
table for a cheaper model to capture, because `gpt-4o-mini`'s own
tokens cost a fraction of a cent to begin with. In this situation the
break-even bar is not merely high, it is *almost unreachable*
(99.99%): with the reference option already this cheap and this
accurate, no realistic amount of additional per-token savings from a
worse model can close the gap. This is the assignment's own
worked example taken to its logical extreme — its Problem A example
(a 10x cheaper model still needing to land within ~1 point of the
expensive one, break-even 91.4%) already shows accuracy dominating
price; this project's own numbers push that further still, because the
"expensive" reference option here is not merely accurate but also
already the cheapest model tested. When a US$9.17 failure cost dwarfs
a fraction-of-a-cent token price, **accuracy is not merely more
important than price, it is nearly the only thing that matters.**

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
| Wasted tokens over one 55-case pass | 0 | ~38,982 |
| Pass rate | unaffected — both candidate tools are never called by the reference solver on any of the 55 cases | unaffected |

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
on `openai/gpt-4o-mini`, the 35 `book` cases that actually see this
observation (`results/cost/d6_observation_size_experiment.json`):

| Metric | Verbose | Compact |
|---|---|---|
| Pass rate | 100.0% (35/35) | 100.0% (35/35) |
| Avg tokens in | 9,136 | 9,105 |
| Avg tokens out | 272 | 268 |
| Avg turns | 4.00 | 4.00 |
| Total cost (35 trials) | US$0.0537 | US$0.0534 |

**Token saving: 0.34%** — real but small at this dataset's scale,
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
expensive to actually run (US$17,404–US$28,979/month) because their
success rate is under 55%; the reference model (`gpt-4o-mini`) is
cheapest overall at US$33.40/month purely because it is nearly always
right. See "Measured: cost per model" and "The switch break-even" above
for the full numbers.

## Which lever dominated THIS project's bill, and how the measurement shows it

Levers 1 and 3 look similar and are not, and this project measured
both precisely enough to say which one actually dominated. **Tool block
size (Experiment 1) is linear in turns**: +178 tokens re-sent on every
single turn, called or not, measured at **~38,982 wasted tokens** over
one full 55-case pass if the two rejected tools had shipped. **Observation
size (Experiment 3) compounds**: a bloated `get_clinic_slots` return is
re-sent on every subsequent turn after the call, not just paid once —
but measured at this dataset's actual scale (few slot rows per query,
short remaining runs after the call), the real difference was only
**~1,085 tokens** across the same 35-trial comparison (31 tokens/trial ×
35 book-case trials). **At this project's measured scale, the LINEAR
lever (tool block size) dominated the bill — by roughly 36×** —
precisely because the COMPOUNDING lever's growth factor (rows returned
× turns remaining) never got large enough here for the theoretical
advantage of "compounds" to overtake the theoretical disadvantage of
"re-sent every turn regardless." This is a genuine, dataset-scale-
dependent finding, not a general rule: D6 Experiment 3's own writeup
already notes the compounding lever would dominate on a busier clinic
dataset returning many more rows per query — the measurement, not an
assumption, is what tells you which lever to spend engineering effort
on for a given deployment's actual traffic shape.

## Which cost lever actually matters most

**Success rate, by a wider margin still.** Experiments 1–3 (tool block,
turn count, observation size) each measure a real but comparatively
small effect (hundreds to tens of thousands of tokens per full pass);
Experiment 4 measures an **~868× swing in monthly cost** between the
best and worst model (US$33.40 to US$28,979, including Layer 3), driven
almost entirely by the fallback term — and the switch break-even
analysis above shows this is not merely large but in this project's
case nearly **unreachable** by any per-token saving alone (a 99.99%
break-even bar for the cheapest-per-token model to clear). At this
problem's scale (US$9.17/failure vs. fractions of a cent per token), no
amount of prompt or tool trimming can close a gap that success rate
alone opens. The practical order of priority this data supports: pick
the highest-success-rate model first, then trim tool/observation bloat as
a secondary, much smaller optimization once that choice is made.
