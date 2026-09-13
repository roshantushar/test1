#!/usr/bin/env python3
"""
D2(a) - LARGER VS TRIMMED TOOL SET
====================================================================
The assignment asks, per candidate tool: does the system genuinely need
it, could it be confused with another tool, and what cost does it add
even when unused? This script makes the LAST question measurable: it
builds a "larger" tool set by adding two plausible-looking but
UNNECESSARY tools to the current, "shortest defensible" seven, and
measures the token cost every single turn of every single run would pay
for them - whether or not they are ever called.

THE TWO CANDIDATE ADDITIONS, and why each fails the first two questions
before it fails the third:

  get_specialty_info(specialty)
    Returns the specialty's name/mandatory_tests/red_flag_terms/treats
    directly. FAILS "does the system need it": check_referral_criteria
    already returns everything the agent needs FROM this data (missing
    tests, red flag match, department match) as pre-computed facts - the
    agent never needs the specialty's raw rule tables, only their
    verdicts. FAILS "could it be confused": an agent given both tools
    could easily call this one and try to re-derive red_flag_term /
    missing_tests itself from the raw lists, redoing (and risking getting
    wrong) work check_referral_criteria already did correctly.

  list_all_specialties()
    Returns every specialty code in the system. FAILS "does the system
    need it": every referral already NAMES its specialty
    (`referrals.json`'s `specialty` field) - there is never a scenario in
    this problem where the agent needs to enumerate specialties it was
    not already told.

Neither tool is added to tools.REGISTRY - they exist only as descriptor
text for this measurement, so this script cannot accidentally make the
real system worse; it only measures what NOT adding them saves.
====================================================================
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import prompt  # noqa: E402
import tools  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "descriptors")

UNNECESSARY_DESCRIPTORS = {
    "get_specialty_info": {
        "name": "get_specialty_info",
        "purpose": "Return the specialty's full rule set: name, mandatory "
                   "tests, red flag terms, and treated conditions.",
        "when": "Whenever you want to inspect the raw protocol rules "
                "directly, instead of relying on check_referral_criteria's "
                "verdicts.",
        "args": {"specialty": "str, the specialty code"},
        "returns": "{code, name, mandatory_tests, red_flag_terms, treats}",
        "failure": "Returns None if the specialty code does not exist.",
    },
    "list_all_specialties": {
        "name": "list_all_specialties",
        "purpose": "Return every specialty code known to the system.",
        "when": "Whenever you want to see what specialties exist.",
        "args": {},
        "returns": "a list of specialty code strings",
        "failure": "Never fails.",
    },
}


def _build(with_extras):
    names = sorted(tools.REGISTRY)
    descriptors = dict(tools.DESCRIPTORS)
    described = [descriptors[n] for n in names if n in descriptors]
    parts = [prompt.RULES_V2, "", "TOOLS AVAILABLE", ""]
    parts += [prompt.format_descriptor(d) for d in described]
    if with_extras:
        parts += [prompt.format_descriptor(d) for d in UNNECESSARY_DESCRIPTORS.values()]
    parts.append(prompt._HOW_TO_ANSWER_CORE + prompt._HOW_TO_ANSWER_SCHEMA)
    return "\n".join(parts)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    trimmed = _build(with_extras=False)
    larger = _build(with_extras=True)

    trimmed_chars, larger_chars = len(trimmed), len(larger)
    trimmed_tok, larger_tok = trimmed_chars // 4, larger_chars // 4
    overhead_tok = larger_tok - trimmed_tok

    # Tie to D6: this overhead is paid on EVERY turn of EVERY run, not
    # once. Use this project's own measured turn counts (D1: median 2,
    # book-track worst case 5) to show the compounding cost over one full
    # 45-case evaluation pass.
    import statistics
    scripted_path = os.path.join(HERE, "..", "..", "results", "scripted", "final_eval.json")
    with open(scripted_path, encoding="utf-8") as fh:
        scripted = json.load(fh)
    total_turns_one_pass = sum(r["record"]["turns"] for r in scripted["results"]
                               if r["trial"] == 1)  # one pass = trial 1 of each case
    wasted_tokens_one_pass = overhead_tok * total_turns_one_pass

    result = {
        "trimmed_tool_count": len(tools.REGISTRY),
        "larger_tool_count": len(tools.REGISTRY) + len(UNNECESSARY_DESCRIPTORS),
        "trimmed_chars": trimmed_chars, "trimmed_tokens_est": trimmed_tok,
        "larger_chars": larger_chars, "larger_tokens_est": larger_tok,
        "overhead_tokens_est_per_turn": overhead_tok,
        "total_turns_one_45case_pass": total_turns_one_pass,
        "wasted_tokens_est_one_45case_pass": wasted_tokens_one_pass,
        "unnecessary_tools_added_for_this_measurement": list(UNNECESSARY_DESCRIPTORS),
        "never_called_by_reference_solver": True,
        "note": "Both candidate tools are never called by "
                "backends.ScriptedPolicyBackend on ANY of the 45 real "
                "cases, because their function is already covered by "
                "check_referral_criteria's pre-computed verdicts or by the "
                "referral's own `specialty` field. Their entire cost "
                f"({overhead_tok} tokens/turn est.) is pure overhead across "
                "every turn of every run - this is the concrete version of "
                "D6's 'tool block size' cost lever.",
    }
    with open(os.path.join(OUT_DIR, "tool_set_comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
