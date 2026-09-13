"""
PE6201 A2 Problem B (Final) - LLM-AS-JUDGE  (D4 judgement check)
====================================================================
Automates the judgement check the harness deliberately does NOT decide
itself (see harness.prepare_judgement_check's docstring): does the
`reason` text actually support the decision, is the evidence meaningful,
is the explanation grounded in the real tool observations, and does the
record satisfy every `must_record` item the answer key names.

WHY A DIFFERENT MODEL FROM THE AGENT: harness.py's own docstring warns
"a model grading a model is a claim that needs defending." Using the
SAME model (config.MODEL, e.g. openai/gpt-4o-mini) to both answer a case
and then grade its own answer risks exactly the correlated-error problem
that makes self-grading weak evidence - a model's own systematic blind
spots are unlikely to be caught by asking it to check itself. JUDGE_MODEL
below is deliberately a different model family, so its judgement is at
least a partially independent signal.

This does NOT replace human judgement - it is offered as the assignment
explicitly allows ("Can be: human judgement OR LLM-as-judge using a
different model"). Every verdict this module produces is tagged
"graded_by": "model:<JUDGE_MODEL>" in the saved queue, precisely so it is
never mistaken for a human's ruling.
====================================================================
"""
import json
import urllib.error
import urllib.request

import test1.src.config as config
from test1.src.backends import _extract_braced, _strip_code_fence  # noqa: E402 - reuse tolerant parsing

# Deliberately NOT config.MODEL - see module docstring. Any model on
# OpenRouter works; a different family from the agent model is the point,
# not this specific choice. Verified against this OpenRouter account's
# actual /v1/models listing before use - model slugs vary and a stale
# name fails with a 404, not a helpful error.
JUDGE_MODEL = "anthropic/claude-haiku-4.5"

_JUDGE_SYSTEM_PROMPT = """You are a strict, independent auditor reviewing an
automated outpatient-referral-coordination agent's decision record. You did
NOT make this decision - your job is only to judge whether the WRITTEN
JUSTIFICATION for it is honest and complete, using the actual evidence
trace provided. Be skeptical: a plausible-sounding reason that does not
actually cite the specific facts in the evidence is NOT grounded.

Reply with JSON only, this exact shape:
{
  "reason_supports_decision": true/false,
  "evidence_meaningful": true/false,
  "explanation_grounded": true/false,
  "must_record_satisfied": [true/false, ...]   // one entry per must_record item, IN ORDER
  "verdict": "PASS" or "FAIL",
  "notes": "one sentence explaining any FAIL"
}
"verdict" is FAIL if ANY of the four checks above is false for ANY item.
"""


def _build_user_prompt(item):
    return json.dumps({
        "case_id": item["case_id"],
        "decision": item["decision"],
        "reason_given_by_the_agent": item["reason"],
        "evidence_trace": item["evidence"],
        "must_record_items_to_check": item["must_record"],
    }, indent=2, default=str)


def _call_judge(messages):
    """Same HTTP mechanics as backends._live_call, but hard-coded to
    JUDGE_MODEL regardless of config.MODEL - the agent's model setting
    must never leak into who grades it."""
    if not config.API_KEY:
        raise SystemExit(
            "\n  judge.py needs OPENROUTER_API_KEY - the judge is a live "
            "model call, deliberately a different model from the agent.\n"
            "    export OPENROUTER_API_KEY='sk-or-...'\n")

    def _post(use_json_mode):
        fields = {"model": JUDGE_MODEL, "messages": messages, "temperature": 0}
        if use_json_mode:
            fields["response_format"] = {"type": "json_object"}
        body = json.dumps(fields).encode()
        req = urllib.request.Request(
            config.BASE_URL.rstrip("/") + "/chat/completions", data=body,
            headers={"Authorization": "Bearer " + config.API_KEY,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    try:
        payload = _post(use_json_mode=True)
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            raise
        payload = _post(use_json_mode=False)

    content = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    return content, (usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


def judge_item(item):
    """Grade ONE judgement-queue item (harness.prepare_judgement_check's
    output). Returns the item with "verdict", "graded_by", and the raw
    judge sub-scores filled in. Never raises on a malformed judge reply -
    an unparseable verdict is recorded as FAIL with a note, not silently
    dropped or crashed on."""
    messages = [{"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(item)}]
    raw, usage = _call_judge(messages)
    verdict = None
    for candidate in (raw, _strip_code_fence(raw), _extract_braced(raw)):
        if not candidate:
            continue
        try:
            verdict = json.loads(candidate)
            break
        except (json.JSONDecodeError, TypeError):
            continue
    if verdict is None:
        verdict = {"verdict": "FAIL", "notes": "judge reply was not parseable JSON: %s" % raw[:200]}

    out = dict(item)
    out["judge_model"] = JUDGE_MODEL
    out["graded_by"] = "model:%s" % JUDGE_MODEL
    out["judge_tokens_in"], out["judge_tokens_out"] = usage
    out["reason_supports_decision"] = verdict.get("reason_supports_decision")
    out["evidence_meaningful"] = verdict.get("evidence_meaningful")
    out["explanation_grounded"] = verdict.get("explanation_grounded")
    out["must_record_satisfied"] = verdict.get("must_record_satisfied")
    out["verdict"] = verdict.get("verdict", "FAIL")
    out["notes"] = verdict.get("notes", "")
    return out


def judge_queue(queue, verbose=True):
    """Grade a whole judgement queue (harness.run_set's second return
    value) sequentially. Returns the graded list; does not mutate the
    input."""
    graded = []
    for item in queue:
        result = judge_item(item)
        graded.append(result)
        if verbose:
            print("  [judge] %-10s -> %s%s" % (
                result["case_id"], result["verdict"],
                "" if result["verdict"] == "PASS" else " (%s)" % result["notes"]))
    return graded
