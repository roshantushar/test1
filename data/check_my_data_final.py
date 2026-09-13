#!/usr/bin/env python3
"""
PE6201 A2 Problem B (Final) - check my data
====================================================================
A COPY of the official checker (A2_reference_data/check_my_data.py),
restricted to Problem B and pointed at this project's extended data
folder. VALIDATION RULES ARE UNCHANGED from the original - only the
paths and the Problem-A machinery (irrelevant here) are removed. The
four checks are identical in meaning:

  1. an id that resolves to nothing
  2. a shipped row that changed
  3. a duplicate id
  4. a case with no label, or a label with no case

Run after every change to make_fixtures_B_final.py or
expected_outcomes_B.json:

    python3 data/make_fixtures_B_final.py
    python3 data/check_my_data_final.py

Exit code 0 = the data hangs together.
====================================================================
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_B = os.path.join(HERE, "generated", "data_B")
KEY_PATH = os.path.join(HERE, "expected_outcomes_B.json")

IDS = {
    "specialties": "code", "urgency_bands": "band",
    "clinic_slots": ("clinic", "date", "time"),
    "patients": "patient_id", "contacts": "patient_id",
    "referrals": "referral_id",
}

LINKS = [
    ("referrals", "patient_id", "patients", "patient_id"),
    ("referrals", "specialty", "specialties", "code"),
    ("clinic_slots", "specialty", "specialties", "code"),
    ("clinic_slots", "band", "urgency_bands", "band"),
    ("patients", "existing_appointments[].specialty", "specialties", "code"),
    ("contacts", "patient_id", "patients", "patient_id"),
]

DECISIONS = {"book", "request_information", "escalate"}

problems, warnings = [], []


def fail(msg):
    problems.append(msg)


def warn(msg):
    warnings.append(msg)


def load(table):
    path = os.path.join(DATA_B, table + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def row_id(table, row):
    k = IDS[table]
    if isinstance(k, tuple):
        return "|".join(str(row.get(x, "?")) for x in k)
    return str(row.get(k, "?"))


def fingerprint(row):
    return hashlib.sha1(
        json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:10]


def values_at(row, path):
    if "[]." in path:
        outer, inner = path.split("[].")
        return [item.get(inner) for item in row.get(outer, []) or []]
    v = row.get(path)
    return [] if v is None else [v]


# Fingerprints of the SHIPPED B rows only - copied verbatim from
# A2_reference_data/check_my_data.py's SHIPPED["B"] block.
SHIPPED_B = json.loads(r"""{
 "clinic_slots": {
  "CARD-C1|2026-09-16|08:30": "dabba78e36",
  "CARD-C1|2026-09-18|15:00": "634ab457f7",
  "CARD-C2|2026-10-21|10:00": "bb64db45fe",
  "CARD-C3|2026-09-25|09:30": "1fe06d294a",
  "DER-C1|2026-09-30|10:40": "ebb187ba8d",
  "DER-C1|2026-10-19|09:00": "50d8a3d0fa",
  "DER-C2|2026-09-24|11:00": "5d617c8553",
  "ENT-C1|2026-10-21|13:20": "5bc04c8b85",
  "ENT-C1|2026-11-10|09:40": "5eea478cf7",
  "ENT-C2|2026-10-06|14:00": "913816a75e",
  "OPH-C1|2026-09-15|09:40": "77c59742fa",
  "OPH-C1|2026-09-22|10:00": "2853f6161b",
  "OPH-C2|2026-09-23|11:20": "dfbfb3bb20",
  "OPH-C2|2026-09-30|11:20": "fef9c97523",
  "OPH-C2|2026-10-14|11:20": "ffc1cef472",
  "OPH-C2|2026-10-14|14:00": "955609b2c8",
  "OPH-C2|2026-10-28|09:00": "6ef2a9d577",
  "OPH-C3|2026-09-29|10:00": "042bc188ce",
  "ORT-C1|2026-10-07|09:20": "dd4fbf7f9e",
  "ORT-C1|2026-10-21|11:00": "08bf8f1ab5",
  "ORT-C2|2026-09-17|14:40": "539e0144f6",
  "ORT-C3|2026-09-28|15:00": "a2acf4109a"
 },
 "contacts": {
  "P-1180": "42aff4fa85", "P-1192": "843344f621", "P-1204": "72f60a4746",
  "P-1215": "1ddc43a73c", "P-1227": "93961f8ff5", "P-1233": "b0d3882d03",
  "P-1241": "610a048d02"
 },
 "patients": {
  "P-1180": "0140f59bb4", "P-1192": "f17b6ca50c", "P-1204": "a426020cbf",
  "P-1215": "d6055e62c6", "P-1227": "2256153ad1", "P-1233": "8bccef209e",
  "P-1241": "7240d6b509"
 },
 "referrals": {
  "REF-5590": "e56c876954", "REF-5602": "e222b4ba7c", "REF-5614": "ccdd4a9580",
  "REF-5620": "ee85d3adff", "REF-5631": "1f6fcbdabf", "REF-5645": "55dc19c516",
  "REF-5658": "162f0608d7", "REF-5663": "e6881209ab", "REF-5671": "247760df79",
  "REF-5684": "c7f7d448eb", "REF-5697": "c11fc37093", "REF-5703": "3c79a0c200",
  "REF-5711": "3689622e2c", "REF-5725": "aab995868e", "REF-5738": "eee6e95467"
 },
 "specialties": {
  "CARD": "d5b312b516", "DER": "44f8a7d1bb", "ENT": "6dbd72eded",
  "OPH": "3fe6b7234b", "ORT": "e38dec8030"
 },
 "urgency_bands": {
  "routine": "5e30a5d72a", "soon": "b5d685efd8", "urgent": "2b641290d0"
 }
}
""")


def main():
    print("Checking PE6201_A2_ProblemB_Final data ...")
    tables = {t: load(t) for t in IDS}
    if any(v is None for v in tables.values()):
        sys.exit("\nMissing data_B/*.json - run make_fixtures_B_final.py first.")

    for name in sorted(tables):
        print("   %4d  %s" % (len(tables[name]), name))

    # 3 - duplicate ids
    for table, rows in tables.items():
        seen = {}
        for row in rows:
            rid = row_id(table, row)
            if rid in seen:
                fail("%s: TWO rows share the id %r." % (table, rid))
            seen[rid] = row

    # 1 - every id resolves
    for src, path, dst, dstkey in LINKS:
        known = {r.get(dstkey) for r in tables[dst]}
        for row in tables[src]:
            for v in values_at(row, path):
                if v not in known:
                    fail("%s %s: %s = %r does not exist in %s.json"
                         % (src, row_id(src, row), path, v, dst))

    # 2 - shipped rows unchanged
    for table, prints in SHIPPED_B.items():
        have = {row_id(table, r): fingerprint(r) for r in tables[table]}
        for rid, fp in prints.items():
            if rid not in have:
                fail("%s: shipped row %r has been DELETED." % (table, rid))
            elif have[rid] != fp:
                fail("%s: shipped row %r has been EDITED." % (table, rid))

    # notes
    have_contacts = {c["patient_id"] for c in tables["contacts"]}
    for p in tables["patients"]:
        if p["patient_id"] not in have_contacts:
            warn("patients %s has no row in contacts.json." % p["patient_id"])
    bands = {b["band"] for b in tables["urgency_bands"]}
    served = {s["band"] for s in tables["clinic_slots"]}
    for b in bands - served:
        warn("urgency band %r has no clinic slots at all." % b)

    # 4 - labels
    if not os.path.exists(KEY_PATH):
        warn("expected_outcomes_B.json not found - skipping the label check.")
    else:
        key = json.load(open(KEY_PATH, encoding="utf-8"))
        labelled = {}
        for row in key:
            cid = row.get("case_id")
            if cid in labelled:
                fail("answer key: %r is labelled twice." % cid)
            labelled[cid] = row
        cases = {r["referral_id"] for r in tables["referrals"]}

        for cid in sorted(cases - set(labelled)):
            fail("%s has no label - it cannot be scored." % cid)
        for cid in sorted(set(labelled) - cases):
            fail("expected_outcomes_B.json labels %r, but no such record exists." % cid)

        for cid, row in labelled.items():
            dec = row.get("expected_decision")
            if dec not in DECISIONS:
                fail("%s: expected_decision %r is not one of %s" % (cid, dec, sorted(DECISIONS)))
            if dec == "escalate" and not row.get("trigger"):
                fail("%s: an escalation with no single trigger." % cid)
            if dec == "request_information" and not row.get("missing"):
                fail("%s: a request with nothing named." % cid)
            if dec == "book" and not row.get("booked"):
                fail("%s: a booking with no clinic, date and time." % cid)

    print()
    for w in warnings:
        print("  note  " + w)
    for p in problems:
        print("  FAIL  " + p)

    if problems:
        print("\n%d problem(s). Fix these before trusting a single result." % len(problems))
        return 1
    print("\nData hangs together%s." % ("  (%d note(s) above)" % len(warnings) if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
