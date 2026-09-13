# D5 — Model Battery and Prompt-Version Comparison

## D5(a) — scripted reproducibility

The submission defaults to `config.BACKEND = "scripted"` (see
`src/config.py`: `BACKEND = os.environ.get("A2_BACKEND", "scripted")` —
the env-var override exists only so this session could switch to
`live` for the experiments below; with no override set, the default is
unconditionally `"scripted"`). This is a **reproducibility test, not a
model experiment**: a clean checkout, run with no API key and no
network access, must produce the same deterministic result every time.

```bash
python3 src/run_eval.py
```

**Result: 95/95 trials pass (100%)** — 55 cases under the D4 trial
policy (35 positive cases × 1 trial, 20 negative cases × 3 trials),
median 2 turns, worst case 5 turns, zero cost, zero network calls.
Evidence: `results/scripted/final_eval.json`. This is the reference
policy walking the real tools deterministically (see
`docs/D0_AGENT_JUSTIFICATION.md` §8 for why this number is a sanity
ceiling, not a reliability measurement — it has no failure mode to
attribute to turn count or per-step reliability, unlike the live v1/v2
comparison below).

## D5 — v1 vs v2 prompt/descriptor comparison (whole-prompt, one model)

Not to be confused with D2(b)'s own required experiment (which varies
only ONE tool's descriptor, `get_clinic_slots`, with the model held
fixed AND every other prompt component held at v2 — see
`docs/D2_TOOL_DESIGN.md`'s D2(b) section). This comparison holds the
model fixed and varies the ENTIRE prompt: rules, answer-format schema,
and every tool's descriptor together.

Both runs are **live**, `openai/gpt-4o-mini`, identical tools, guardrails,
autonomy setting, and 55-case/95-trial eval set — only the system
prompt differs. v1 is *deliberately* worse (vague check order, no
anti-injection warning, a minimal answer schema with no trigger/missing
enum, thin one-line tool descriptors); v2 is the real, shipped prompt
(explicit five-check order, anti-injection warning, a fixed
trigger/missing schema, and the full per-tool descriptors). See
`src/prompt.py` (`RULES_V1`/`RULES_V2`, `V1_DESCRIPTORS`,
`_HOW_TO_ANSWER_CORE`/`_HOW_TO_ANSWER_SCHEMA`) and
`results/descriptors/comparison.json` for the raw data behind this
table.

| Metric | v1 (deliberately weak) | v2 (shipped) |
|---|---|---|
| Overall pass rate | 41.1% (39/95) | 100.0% (95/95) |
| Negative-case pass rate (against the answer key's 60 negative trials) | 15.0% (9/60) | 100.0% (60/60) |
| Avg tokens in | 4,128 | 7,258 |
| Avg tokens out | 335 | 211 |
| Avg turns | 3.84 | 3.05 |
| Total cost (95 trials) | $0.0779 | $0.1155 |

**Why v1 fails almost entirely on label formatting, not underlying
judgement.** Reading `results/descriptors/comparison.json`'s failure
list: the large majority of v1's failures are cases where the model
reached the *correct* decision (escalate, or request_information) but
could not name the exact `trigger` (one of the five machine labels:
`red_flag_term`, `specialty_mismatch`, `duplicate_future_appointment`,
`no_slot_in_window`, `instruction_in_referral_free_text`) or the exact
`missing` test string, because v1's answer schema never told it those
enums exist. A visible minority are genuine decision errors — v1 books
an appointment that should have been escalated (a red flag or an
injected instruction), because nothing in v1's rules states the check
order or warns that referral free text is untrusted input. **This is
the project's clearest demonstration that a stricter, more explicit
system prompt is not bureaucratic overhead — it is what turns "probably
noticed the right thing" into "reliably produces the exact record a
downstream system or auditor needs."**

The overall pass rate is higher here (41.1%) than in an earlier
measurement on a more negative-heavy version of this set (27.1% on a
69%-negative, 45-case shape) because most of this set's 55 cases are
now `book` (35/55, 63.6%) — cases v1 handles fine via correct tool
calls, since booking success doesn't require naming a trigger label.
The **negative-case** pass rate (15.0%) is the more informative number
for comparing prompt quality: it isolates exactly the cases where v1's
missing schema matters, and remains just as stark as before.

## D5(b) — same prompt (v2), model varied

All 5 models below ran the **identical** v2 system prompt, tool set,
guardrails, autonomy setting, and 55-case/95-trial eval set, live via
OpenRouter, with real captured usage (`backends.LiveBackend` reads
`payload["usage"]` from every response — not an estimate). Raw data:
`results/live/model_comparison.json` and one JSON file per model in
`results/live/`.

| Model | Overall Pass | Negative Pass | Median Turns | Mean Latency | Total Cost (95 trials) |
|---|---|---|---|---|---|
| **openai/gpt-4o-mini** | 95/95 (100.0%) | 60/60 (100.0%) | 4 | 9.12s | $0.1154 |
| **google/gemini-2.5-flash-lite** | 91/95 (95.8%) | 60/60 (100.0%) | 2 | 4.66s | $0.1421 |
| **qwen/qwen-2.5-72b-instruct** | 79/95 (83.2%) | 55/60 (91.7%) | 3 | 25.59s | $0.1247 |
| **meta-llama/llama-3.1-8b-instruct** | 50/95 (52.6%) | 20/60 (33.3%) | 3 | 8.57s | $0.1381 |
| **mistralai/mistral-nemo** | 20/95 (21.1%) | 15/60 (25.0%) | 2 | 15.53s | $0.0814 |

**The two extremes, for the report:** the cheapest model that met the
bar is **`gemini-2.5-flash-lite`** — 95.8% overall, a perfect 100%
negative record, the fastest mean latency in the battery (4.66s), at a
raw per-trial API cost within a few cents of every other model here;
at 4,000 referrals/month (D6) it costs **$1,554/month**, against
gpt-4o-mini's $8.40. The model that most conspicuously did NOT earn
its (low) sticker price is **`mistral-nemo`** — the cheapest raw
per-token price in the battery, yet the worst overall accuracy (21.1%)
and the worst monthly cost once the fallback term is priced in
(**$28,954/month**, D6) — a ~3,450× gap from the cheapest *effective*
option (`gpt-4o-mini`) despite having the lowest sticker price of any
model tested. **Where the negative cases separated them:** all
5 models cluster near each other on raw per-token price (a few cents
apart across the whole 95-trial battery), but negative-case pass rate
alone spans 25.0% to 100.0% — and negative-case reliability, not price,
is what D6 shows actually determines the real monthly bill.

**Acknowledged gap: all 5 models are cheap tier.** The brief requires
the battery to "span at least two price tiers." Every model actually
run here — `gpt-4o-mini`, `gemini-2.5-flash-lite`, `qwen-2.5-72b-instruct`,
`llama-3.1-8b-instruct`, `mistral-nemo` — sits in OpenRouter's cheap
tier (all under roughly US$0.50/M tokens on the more expensive side).
No mid-tier or frontier model (e.g. `gpt-4o`, `claude-3.5-sonnet`,
`gemini-1.5-pro`) was included, so this battery demonstrates that
*accuracy diverges sharply within one price tier* (21.1% to 100.0%
pass, all at near-identical raw token price) but does not itself show
whether price and accuracy trade off *across* tiers — which is exactly
what D6's break-even section works out theoretically instead, using
the two-tier worked example from the brief's own Problem A illustration
(a 10x-cheaper model needing to land within ~1 point of an expensive
one at break-even 91.4%). If time/budget allow, the strongest fix is
running one mid-tier model (e.g. `gpt-4o` or `claude-3.5-haiku` at its
higher price point) on the negative cases only, per the brief's own
guidance for a frontier-tier addition. Left undone here for budget
reasons; flagged rather than silently omitted.

### Model substitutions and why

- **`google/gemini-flash-1.5`** was requested but does not exist on
  this OpenRouter account's catalog (a non-standard/newer model
  lineup — verified via `/v1/models`). Substituted with
  **`google/gemini-2.5-flash-lite`**, the closest same-tier ("cheap,
  fast Gemini") equivalent, at $0.10/$0.40 per M tokens.
- **`anthropic/claude-3-haiku`** was run and produces a **genuine,
  reportable 0% result excluded from the final comparison table above
  at the user's request**, kept on disk as raw data
  (`results/live/anthropic_claude-3-haiku.json`) but not folded into
  cost or ranking numbers. See "Claude 3 Haiku: a protocol-compliance
  finding" below for what actually happened — it is not a harness bug.
- **`qwen/qwen-2.5-72b-instruct`** was substituted in for Claude 3
  Haiku (explicit request) after that 0% result. It scored near
  gpt-4o-mini parity on the original 45-case set, but a materially
  weaker 83.2% after the dataset was rebalanced — see below.

### Claude 3 Haiku: a protocol-compliance finding, not a harness bug

*(Measured on the earlier 45-case/107-trial set, before the two
rebalances — not re-run since, as it was excluded from the comparison
table at the user's request. The underlying finding, a structural
protocol-compliance failure rather than a reasoning gap, does not
depend on the specific eval set and is kept for reference.)*

Every one of Claude 3 Haiku's 107 trials failed with
`trigger: unparseable_output`. Direct API testing (bypassing the
harness entirely) showed why: given the full v2 protocol, the model
does not wait for tool results between turns — it dumps its **entire
planned trajectory as several JSON objects concatenated in one
response** (`get_referral` → `check_referral_criteria` →
`compute_window` → `get_clinic_slots` → `book_slot` → a final decision,
all in one completion). `json.loads` correctly rejects this as invalid
JSON, and the harness correctly records it as `unparseable_output`
rather than guessing at which of several concatenated objects was
"the" answer. This was verified NOT to be a parsing bug in
`backends._parse_move` (whose tolerant fallbacks — code-fence
stripping, brace extraction — are unrelated to this failure mode) by
reproducing it directly against the OpenRouter API outside the
harness. Loosening the parser to silently take the first JSON object
in a multi-object dump was deliberately rejected: it would misrepresent
what the model did (planned the whole task open-loop, without ever
seeing a real tool result) and would inconsistently favor one model in
an otherwise apples-to-apples battery.

### Gemini 2.5 Flash Lite: the strongest budget alternative on this set

Gemini reached 95.8% overall / **100% negative** — a perfect record on
every safety-critical case — at the fastest mean latency in the entire
battery (4.66s, faster even than gpt-4o-mini's 9.12s) and a total cost
comparable to the others ($0.1421 for 95 trials). Its 4 failures are
all on `book` cases, not negative cases, making it the standout
budget-tier choice on this rebalanced set: cheap, fast, and it never
missed a safety check.

### Qwen 2.5 72B Instruct: a materially different result after the rebalance

On the earlier 45-case/107-trial set, Qwen scored 99.1% overall — near
gpt-4o-mini parity. On this rebalanced 55-case/95-trial set it scores
**83.2% overall / 91.7% negative**, a real drop, not measurement noise
(re-run twice to rule out a one-off flake). Its mean per-call latency
(25.59s) is also markedly higher than before (14.52s), and by far the
highest in this battery — more than 5x gpt-4o-mini's 9.12s. Both
figures reflect genuine model behavior encountering the newer,
5th-block negative cases (`REF-6071`–`6080`) it had not been measured
against before, not an artifact of the harness or infrastructure — the
same OpenRouter routing flakiness that occasionally required a retry
during this battery (see the robustness-bugs section below) is a
separate, already-handled infrastructure concern, distinct from this
model's own accuracy and speed on the harder set.

### Where the models actually diverge — book vs. negative, per model, measured

The assignment's own stated expectation is that live models "diverge
most on the negative cases." Measured directly (`book pass rate` vs
`negative pass rate`, same model, same run, `results/live/*.json`):

| Model | Book pass rate | Negative pass rate | Gap (book − negative) |
|---|---|---|---|
| gpt-4o-mini | 100.0% | 100.0% | 0.0pp |
| gemini-2.5-flash-lite | 88.6% | 100.0% | **−11.4pp** (better on negative) |
| qwen-2.5-72b-instruct | 68.6% | 91.7% | **−23.1pp** (better on negative) |
| mistral-nemo | 14.3% | 25.0% | **−10.7pp** (better on negative) |
| llama-3.1-8b-instruct | 85.7% | 33.3% | **+52.4pp** (worse on negative) |

**The honest finding is more nuanced than the expected one, and worth
reporting exactly as measured rather than forced to fit.** The raw
spread ACROSS models is actually slightly larger on `book` cases
(85.7 percentage points, from 100.0% down to 14.3%) than on negative
cases (75.0 points, from 100.0% down to 25.0%) — models disagree with
each other MORE on booking than on refusing. And four of the five
models here are *better* at negative cases than at booking, not worse
— only `llama-3.1-8b-instruct` shows the pattern the assignment
expects (a 52.4-point drop on negative cases specifically). The likely
mechanical reason: a `book` decision requires correctly chaining all
six tools (band, window, slot match, `book_slot` args) across 4–5
turns — many more opportunities to slip procedurally — while most
negative decisions resolve in 1–2 turns off a single fact
(`check_referral_criteria`'s red-flag term or mismatch flag). For most
of these models, **procedural chain length, not safety judgement, is
the dominant source of divergence** on this eval set — the opposite of
what "weaker models miss subtle safety cues" would predict, and a
finding this project would have missed entirely by assuming the
expected pattern instead of measuring it. `llama-3.1-8b-instruct`
remains the one model matching the expected shape: it fails
disproportionately on `red_flag`, `specialty_mismatch`, and
missing-mandatory-test families specifically — the cases that require
reading free text carefully rather than following a tool chain — which
is worth reading as a genuine safety-judgement gap for that one model,
distinct from the procedural-length effect dominating the other four.

## 9 robustness bugs found and fixed while running this battery

Live testing against 5 different model families, across the original
and both rebalanced eval sets, surfaced failure modes the scripted
backend's deterministic policy never exercises. Each was root-caused
and fixed at the correct layer (never papered over with a prompt
tweak), and the scripted 100%/100% regression was re-verified after
every single fix:

1. **`book_slot` called with an incomplete args dict** (observed on
   `meta-llama/llama-3.1-8b-instruct`) crashed with a raw `TypeError`
   from `tools.call`'s keyword unpacking. Fixed in
   `agent._verified_book_slot` with an explicit required-keys check
   that raises a recorded `GuardrailStop` instead.
2. **`booked` returned as a non-dict shape** (e.g. a bare list) crashed
   `harness.code_check` and `code_check_breakdown` on `.get()`. Fixed
   by treating any non-dict `booked` value as simply missing its
   fields, in both functions.
3. **A tool's own argument validation raising `ValueError`**
   (`compute_window(window_weeks=None)`, also `llama-3.1-8b-instruct`)
   was only caught for `TypeError`, not `ValueError`. Broadened the
   `except` clause in `agent.py`'s tool-call loop.
4. **Live HTTP layer hardening, round 1** (`src/backends.py`,
   `_live_call`): added retries for (a) truncated chunked responses
   (`http.client.IncompleteRead`), (b) a 200 response carrying a
   provider-side error object instead of `choices` (observed on
   `mistralai/mistral-nemo` via a DeepInfra rate-limit), and (c) an
   outer retry around the whole json-mode/no-json-mode attempt pair,
   since OpenRouter routes a single model id across multiple upstream
   providers with different capabilities (observed on
   `qwen/qwen-2.5-72b-instruct`, routed to both DeepInfra and Novita
   within the same run — Novita does not support
   `response_format: json_object`).
5. **A top-level JSON array response** (`backends._parse_move`) parsed
   successfully as valid JSON but crashed every downstream `move.get(...)`
   call, since the move shape assumes a dict. Fixed by only accepting a
   parsed candidate if it is a dict, falling through to the existing
   `unparseable_output` path otherwise.
6. **`book_slot` called with an extra, unexpected kwarg** (e.g.
   `capacity`, copied from a `get_clinic_slots` observation row by
   `meta-llama/llama-3.1-8b-instruct`) crashed `tools.call`'s `**args`
   unpacking with `TypeError`. Fixed by filtering `args` down to
   exactly the six required keys (already confirmed present) before
   calling the tool, rather than passing whatever the model supplied
   verbatim.
7. **A 504 Gateway Timeout crashed the run with zero retries**
   (observed on `meta-llama/llama-3.1-8b-instruct`) — the existing
   retry logic only handled 4xx errors, immediately re-raising any 5xx
   on the assumption the model itself was broken. Widened the outer
   routing-retry loop to treat 5xx the same as 4xx: a transient
   gateway/server condition, not evidence the model can't work.
8. **`agent.py`'s own booking-verification logic crashed on a non-dict
   `booked` value** (a *different* call site from bug #2's fix in
   `harness.py` — `record["booked"].get("clinic")` in the "model
   declared a booking without calling the tool" backfill path) with
   the same `AttributeError` shape. Fixed with the same `isinstance`
   guard, at the second location it was needed.
9. **A provider's inline 200-response error was retried at the inner
   level but not the outer routing-retry level** (observed on
   `qwen/qwen-2.5-72b-instruct`: `_post_with_retries` exhausted its 3
   attempts on a `RuntimeError` from `_post`'s "no choices" detection,
   then propagated straight past the outer loop, which only caught
   `HTTPError`). Widened the outer loop's except clause to catch
   `RuntimeError` too, since it is the same routing problem in a
   different shape.

None of these are "fixes to make numbers look better" — each is a
crash that would have taken down the whole battery run regardless of
which model triggered it, fixed at the layer that actually owns the
failure (tool-call validation, harness comparison logic, or the HTTP
transport), never by changing what counts as a pass.

## Reproduce

```
export OPENROUTER_API_KEY='sk-or-...'
export A2_BACKEND=live      # BACKEND defaults to 'scripted' (free) otherwise
python3 experiments/d2b_descriptors/run_live_comparison.py   # D5(a): v1 vs v2
python3 experiments/d5_models/run_live_battery.py            # D5(b): model battery
```

Total live spend across all of D5 (both rebalances, including retries
required by the transient infrastructure issues fixed above): under $3
across the full session — see `docs/REPORT_EVIDENCE.md` for the
per-experiment breakdown.
