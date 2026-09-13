#!/usr/bin/env python3
"""
PE6201 A2 Problem B (Final) - ENTRY POINT  (D5a)
====================================================================
    python3 src/run_eval.py                run the full 35-case set, graded
    python3 src/run_eval.py REF-5602        run one case, every turn shown
    python3 src/run_eval.py --prompt        print what a LIVE model would be told
    python3 src/run_eval.py --prompt --v1   the deliberately worse descriptor set

THIS IS WHAT A MARKER RUNS. Clone, `python3 data/make_fixtures_B_final.py`
once to materialise the extended data, then `python3 src/run_eval.py` -
no key, no network, no arguments needed beyond that.
====================================================================
"""
import json
import os
import sys

import test1.src.config as config
from test1.src.harness import load_cases, load_key, report, run_set


def main(argv):
    print()
    print(config.summary())

    args = [a for a in argv[1:] if not a.startswith("-")]
    flags = {a for a in argv[1:] if a.startswith("-")}
    version = "v1" if "--v1" in flags else "v2"

    if "--prompt" in flags:
        import test1.src.prompt as prompt
        print()
        prompt.audit(version)
        return 0

    if args:
        case_id = args[0]
        print()
        print("-" * 68)
        print("  %s - every turn" % case_id)
        print("-" * 68)
        results, queue = run_set([case_id], verbose=True, descriptor_version=version)
        if not results:
            return 1
        print()
        print("  DECISION RECORD")
        print(json.dumps(results[0]["record"], indent=2, default=str)[:2500])
        print()
        print("  CODE CHECK   %s" % ("PASS" if results[0]["passed"] else "FAIL"))
        for f in results[0]["fails"]:
            print("      %s" % f)
        print()
        print("  JUDGEMENT CHECK - not automated. Someone reads the reason:")
        for item in queue[0]["must_record"]:
            print("      [ ] %s" % item)
        print()
        return 0 if results[0]["passed"] else 1

    key = load_key()
    cases = [c for c in load_cases() if c in key]
    print("\n  Running the full evaluation set: %d case(s)." % len(cases))

    if not cases:
        print("\n  Nothing to run. Did you run "
              "`python3 data/make_fixtures_B_final.py` yet?")
        return 1

    results, queue = run_set(cases)
    summary = report(results)

    out_path = os.path.join(config.PROJECT_ROOT, "results", "scripted", "final_eval.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"config": config.summary(), "summary": summary,
                   "results": results, "judgement_queue": queue},
                  fh, indent=2, default=str)
    print("  Wrote %s" % out_path)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
