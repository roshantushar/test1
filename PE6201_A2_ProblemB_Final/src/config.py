"""
PE6201 A2 Problem B (Final) - CONFIGURATION
====================================================================
Vendor-neutral block, following the pattern shown in the read-only
scaffold (A2_scaffold 2/config.py). Reused idea: everything that knows
which model is in use lives here and in backends.py, nowhere else.

    BACKEND = "scripted"   free, deterministic, no key, no network.
                           THIS IS THE COMMITTED DEFAULT (D5a).
    BACKEND = "live"       real model via OpenRouter. Costs money.
                           Only D2(b)'s live comparison and D5(b)'s
                           battery need this.
====================================================================
"""
import os

# ---------------------------------------------------------------------
# THE THREE STRINGS. Change these, change nothing else.
# ---------------------------------------------------------------------
BACKEND = os.environ.get("A2_BACKEND", "scripted")  # "scripted" | "live"

MODEL = "openai/gpt-4o-mini"  # only used when BACKEND == "live"
BASE_URL = "https://openrouter.ai/api/v1"

# Key never lives in this file.
#     export OPENROUTER_API_KEY="sk-or-..."
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# ---------------------------------------------------------------------
# PROBLEM. This implementation only targets Problem B.
# ---------------------------------------------------------------------
PROBLEM = "B"

# ---------------------------------------------------------------------
# GUARDRAIL LIMITS (D3a). Set from evidence gathered in D4/D7, not from
# a round number. See docs/D3_GUARDRAILS.md for why these values.
# ---------------------------------------------------------------------
MAX_TURNS = 8                  # step cap
MAX_TOKENS_PER_RUN = 60000     # budget ceiling
AUTONOMY = "confirm"           # "suggest" | "confirm" | "act"
#   suggest  - the agent proposes; a human does everything
#   confirm  - the agent does everything EXCEPT book_slot, which waits
#              for a yes. The gate sits in front of the irreversible
#              ACTION, not in front of the agent as a whole.
#   act      - the agent completes book_slot itself

# ---------------------------------------------------------------------
# DATA LOCATIONS.
#
# GROUND-TRUTH FIREWALL: this module exposes paths to the SHIPPED
# reference data and to this project's OWN extended data. It does NOT
# read expected_outcomes_B.json for the agent - only harness.py may do
# that, and only for scoring.
# ---------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))                 # .../src
PROJECT_ROOT = os.path.dirname(HERE)                               # .../PE6201_A2_ProblemB_Final
REPO_ROOT = os.path.dirname(PROJECT_ROOT)                          # repo root

# The official, read-only scaffold data (never modified by this project).
_SHIPPED_CANDIDATES = [
    os.environ.get("A2_DATA", ""),
    os.path.join(REPO_ROOT, "A2_reference_data"),
]

# This project's OWN extended data (data/expected_outcomes_B.json,
# data/generated/data_B/*.json) - see data/make_fixtures_B_final.py.
FINAL_DATA_DIR = os.path.join(PROJECT_ROOT, "data")
FINAL_DATA_B_DIR = os.path.join(FINAL_DATA_DIR, "generated", "data_B")

# Whether to run the agent's tools against the shipped data_B/ or against
# this project's extended data_B/ (shipped rows + our additions). The
# extended set is a strict superset built by make_fixtures_B_final.py.
USE_EXTENDED_DATA = True


def shipped_data_root():
    """Locate the folder that holds the official, read-only data_B/."""
    for c in _SHIPPED_CANDIDATES:
        if c and os.path.isdir(os.path.join(c, "data_B")):
            return os.path.abspath(c)
    raise SystemExit(
        "\n  Could not find the shipped reference data.\n"
        "  Looked for a folder containing data_B/ in:\n"
        + "".join("    %s\n" % os.path.abspath(c) for c in _SHIPPED_CANDIDATES if c)
        + "\n  Fix: export A2_DATA=/path/to/A2_reference_data\n")


def data_b_dir():
    """Which data_B/ the tool layer actually reads.

    Defaults to the EXTENDED set (data/generated/data_B/), which is a
    superset of the shipped rows plus this project's additions, produced
    by `python3 data/make_fixtures_B_final.py`. Falls back to the
    shipped folder if the extended one has not been generated yet, so a
    fresh clone still runs.
    """
    if USE_EXTENDED_DATA and os.path.isdir(FINAL_DATA_B_DIR):
        return FINAL_DATA_B_DIR
    return os.path.join(shipped_data_root(), "data_B")


def expected_outcomes_path():
    """The FINAL answer key. Only harness.py should call this."""
    own = os.path.join(FINAL_DATA_DIR, "expected_outcomes_B.json")
    if os.path.exists(own):
        return own
    return os.path.join(shipped_data_root(), "expected_outcomes_B.json")


# ---------------------------------------------------------------------
# PRICES, US dollars per MILLION tokens. Re-checked before any live run.
# Source: OpenRouter listing for MODEL, checked on the day D5(b) is run.
# NOT yet re-verified in this session because no live run has happened -
# see docs/D6_COST_MODEL.md.
# ---------------------------------------------------------------------
PRICE_IN = 0.15
PRICE_OUT = 0.60


def summary():
    where = "FREE, deterministic" if BACKEND == "scripted" else "LIVE - this costs money"
    model = "(no model)" if BACKEND == "scripted" else MODEL
    return ("BACKEND=%s  %s  |  PROBLEM=%s  |  model=%s  |  "
            "cap=%d turns  |  autonomy=%s  |  data=%s"
            % (BACKEND, where, PROBLEM, model, MAX_TURNS, AUTONOMY, data_b_dir()))
