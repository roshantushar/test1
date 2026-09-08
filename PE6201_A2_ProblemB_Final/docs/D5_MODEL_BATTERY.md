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

**Result: 107/107 trials pass (100%)** — 45 cases under the D4 trial
policy (14 positive cases × 1 trial, 31 negative cases × 3 trials),
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
autonomy setting, and 45-case/107-trial eval set — only the system
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
| Overall pass rate | 27.1% (29/107) | 100.0% (107/107) |
| Negative-case pass rate | 26.1% (18/69 negatives under v1's own decision split) | 100.0% (93/93) |
| Avg tokens in | 3,603 | 6,689 |
| Avg tokens out | 302 | 191 |
| Avg turns | 3.47 | 2.77 |
| Total cost (107 trials) | $0.0772 | $0.1197 |

**Why v1 fails almost entirely on label formatting, not underlying
judgement.** Reading `results/descriptors/comparison.json`'s failure
list: the large majority of v1's 78 failures are cases where the model
reached the *correct* decision (escalate, or request_information) but
could not name the exact `trigger` (one of the five machine labels:
`red_flag_term`, `specialty_mismatch`, `duplicate_future_appointment`,
`no_slot_in_window`, `instruction_in_referral_free_text`) or the exact
`missing` test string, because v1's answer schema never told it those
enums exist. A visible minority (e.g. `REF-5590`, `REF-5703`,
`REF-6031`–`6035`) are genuine decision errors — v1 books an
appointment that should have been escalated (a red flag or an injected
instruction), because nothing in v1's rules states the check order or
warns that referral free text is untrusted input. **This is the
project's clearest demonstration that a stricter, more explicit system
prompt is not bureaucratic overhead — it is what turns "probably
noticed the right thing" into "reliably produces the exact record a
downstream system or auditor needs."**

This negative-heavy (69%), five-trigger-type dataset makes the gap far
starker than the project's earlier, mostly-positive 35-case set did
(v1 45.5% there) — with only a handful of negative cases and a single
trigger type, v1's missing schema rarely mattered. The redesigned
50-case set (69% negative, six deliberately distinct failure-mode
blocks) is what actually exercises the schema gap v1 has.

## D5(b) — same prompt (v2), model varied

All 5 models below ran the **identical** v2 system prompt, tool set,
guardrails, autonomy setting, and 45-case/107-trial eval set, live via
OpenRouter, with real captured usage (`backends.LiveBackend` reads
`payload["usage"]` from every response — not an estimate). Raw data:
`results/live/model_comparison.json` and one JSON file per model in
`results/live/`.

| Model | Overall Pass | Negative Pass | Median Turns | Mean Latency | Total Cost (107 trials) |
|---|---|---|---|---|---|
| **openai/gpt-4o-mini** | 107/107 (100.0%) | 93/93 (100.0%) | 2 | 6.35s | $0.1197 |
| **qwen/qwen-2.5-72b-instruct** | 106/107 (99.1%) | 92/93 (98.9%) | 2 | 14.52s | $0.1307 |
| **google/gemini-2.5-flash-lite** | 97/107 (90.6%) | 83/93 (89.2%) | 2 | 3.85s | $0.1348 |
| **meta-llama/llama-3.1-8b-instruct** | 42/107 (39.2%) | 31/93 (33.3%) | 3 | 7.62s | $0.1418 |
| **mistralai/mistral-nemo** | 36/107 (33.6%) | 33/93 (35.5%) | 2 | 6.85s | $0.0958 |

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
  Haiku (explicit request) after that 0% result, and became the
  standout finding of this battery — see below.

### Claude 3 Haiku: a protocol-compliance finding, not a harness bug

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

### Qwen 2.5 72B Instruct: near gpt-4o-mini quality, ~2.3x the latency

Qwen reached 99.1% overall / 98.9% negative — a single non-reproducible
flake apart from perfect agreement with the reference policy — at
essentially the same total cost as gpt-4o-mini ($0.1307 vs $0.1197 for
107 trials). Its mean per-call latency (14.52s) is more than double
gpt-4o-mini's (6.35s), consistent with running as a large open-weight
model rather than a latency-optimized proprietary one. It is the
strongest evidence in this battery that quality on this task is not
gated on being a frontier proprietary model — but latency, not price,
is what would actually cost you if you swapped to it in production.

### Weak models fail hardest on exactly the safety-critical families

Both `llama-3.1-8b-instruct` and `mistral-nemo` fail disproportionately
on `red_flag`, `specialty_mismatch`, and missing-mandatory-test
families — the negative cases that require careful reading of
free-text clinical summaries rather than straightforward tool
sequencing. This is the expected failure shape for smaller models on a
safety-critical task: the mechanical parts (calling tools in the right
order) degrade less than the judgement parts (recognising a red-flag
phrase, or that a referral belongs to the wrong department).

## 4 robustness bugs found and fixed while running this battery

Live testing against 5 different model families surfaced failure modes
the scripted backend's deterministic policy never exercises. Each was
root-caused and fixed at the correct layer (never papered over with a
prompt tweak), and the scripted 100%/100% regression was re-verified
after every single fix:

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
4. **Live HTTP layer hardening** (`src/backends.py`, `_live_call`):
   added retries for (a) truncated chunked responses
   (`http.client.IncompleteRead`, observed against this OpenRouter
   endpoint mid-battery), (b) a 200 response carrying a provider-side
   error object instead of `choices` (observed on
   `mistralai/mistral-nemo` via a DeepInfra rate-limit), and (c) an
   outer retry around the whole json-mode/no-json-mode attempt pair,
   since OpenRouter routes a single model id across multiple upstream
   providers with different capabilities (observed on
   `qwen/qwen-2.5-72b-instruct`, routed to both DeepInfra and Novita
   within the same run — Novita does not support
   `response_format: json_object`).

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

Total live spend across all of D5: ~$0.60 (D5(a) + D5(b), 6 model runs
including the excluded Claude 3 Haiku row).
