#!/usr/bin/env python3
"""
D6 - COST TO SERVE
====================================================================
D5(b)'s live model battery is now complete (5 models, 107 trials each,
real OpenRouter usage) - see results/live/model_comparison.json. This
script therefore reports a MEASURED cost-and-success-rate row per model
(_measured_all_models) as the primary output, in addition to keeping
the original ILLUSTRATIVE 80/90/95/99% sweep (against the scripted
backend's token ESTIMATE) for reference - the sweep still shows how the
cost-model ARITHMETIC responds to success rate in general, independent
of which model is chosen.
====================================================================
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src")
sys.path.insert(0, SRC)

import config  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "..", "results", "cost")
SCRIPTED_RESULTS = os.path.join(HERE, "..", "..", "results", "scripted", "final_eval.json")
LIVE_RESULTS = os.path.join(HERE, "..", "..", "results", "live", "openai_gpt-4o-mini.json")
MODEL_COMPARISON = os.path.join(HERE, "..", "..", "results", "live", "model_comparison.json")


def _n_referrals_in_eval_set():
    """Read the eval set size directly from the answer key rather than a
    hardcoded constant - a hardcoded 45 silently overstated cost-per-
    referral by 55/45 (~1.22x) after the 45->55 case rebalance, since
    every model's total measured cost was divided by the wrong count."""
    sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
    import harness
    return len(harness.load_key())

REFERRALS_PER_MONTH = 4000
FALLBACK_RATE_USD_PER_HOUR = 55.0
FALLBACK_MINUTES = 10.0
FALLBACK_COST_PER_FAILURE = round(FALLBACK_RATE_USD_PER_HOUR / 60.0 * FALLBACK_MINUTES, 4)

ILLUSTRATIVE_SUCCESS_RATES = [0.80, 0.90, 0.95, 0.99]
BASELINE_SUCCESS_RATE = 0.90

# LAYER 3 - fixed monthly cost (storage, infrastructure, eval runs,
# monitoring, maintenance), stated with its assumptions rather than
# omitted, per the assignment's own three-layer model. At this
# project's scale (a stateless Python service with no database beyond
# the local JSON fixtures, one append-only decision log, and a
# scheduled re-run of the 55-case scripted eval set for regression
# monitoring), a small always-on compute instance plus log storage is
# the dominant cost:
#   - light cloud compute (small always-on instance, e.g. a single
#     small VM/container running the agent service): ~US$15/month
#   - log/decision-record storage (results/decision_log.jsonl growing
#     at ~4,000 lines/month, negligible in bytes, rounds to a nominal
#     minimum storage tier): ~US$2/month
#   - scheduled scripted-eval regression runs (D5(a), free per-run
#     since BACKEND=scripted, but the compute minutes to run it on a
#     schedule are counted here): ~US$3/month
#   - basic monitoring/alerting (uptime + error-rate check): ~US$5/month
# Total, stated as an assumption to be revised with real infrastructure
# quotes, not a measurement: US$25/month.
LAYER_3_FIXED_MONTHLY_USD = 25.0


def _mean_estimated_cost_per_case():
    with open(SCRIPTED_RESULTS, encoding="utf-8") as fh:
        data = json.load(fh)
    costs = [r["record"]["cost_usd"] for r in data["results"]]
    return round(statistics.mean(costs), 6), len(costs)


def _measured_one_model():
    """REAL numbers from the one-model live battery (D5b, partial - one
    model, not the full family comparison - see STATUS.md). Only
    computed when results/live/ exists; kept separate from the
    illustrative sweep above rather than replacing it, since one model's
    pass rate is not "the" success rate this agent will ship with."""
    if not os.path.exists(LIVE_RESULTS):
        return None
    with open(LIVE_RESULTS, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data["trials"]
    unique_cases = len({r["case_id"] for r in rows})
    total_cost = sum(r["record"]["cost_usd"] for r in rows)
    # Cost per REFERRAL in production is the cost of processing it ONCE,
    # not the evaluation harness's 3-trials-for-negatives cost - so this
    # divides by unique referrals, not by len(rows) (trials).
    variable_cost_per_referral = round(total_cost / unique_cases, 6)
    s_measured = round(sum(1 for r in rows if r["passed"]) / len(rows), 4)
    expected_fallback = round((1 - s_measured) * FALLBACK_COST_PER_FAILURE, 4)
    cost_per_referral = round(variable_cost_per_referral + expected_fallback, 4)
    return {
        "model": data["summary"]["model"],
        "MEASUREMENT_STATUS": "REAL measured numbers (one model, one prompt "
                              "version) - not the full D5b family comparison.",
        "success_rate_measured": s_measured,
        "success_rate_caveat": ("This is the D4 CODE-CHECK pass rate over "
                               "%d evaluation trials on the CURRENT %d-case "
                               "eval set, for the v2 prompt - not yet a "
                               "large-sample production success rate, and "
                               "not the number for every prompt: the SAME "
                               "model with the deliberately worse v1 "
                               "prompt scores far lower on the identical "
                               "trials (results/descriptors/comparison.json, "
                               "see docs/D5_MODEL_BATTERY.md for the exact "
                               "current figures) - this set is dominated "
                               "by cases needing an EXACT trigger/missing "
                               "label, which v1's schema cannot supply even "
                               "when it reaches the right underlying "
                               "decision. See docs/D4_EVALUATION.md and "
                               "STATUS.md for the full account."
                               % (len(rows), unique_cases)),
        "variable_model_cost_per_referral_usd_MEASURED": variable_cost_per_referral,
        "expected_fallback_cost_per_referral_usd": expected_fallback,
        "cost_per_referral_usd": cost_per_referral,
        "monthly_cost_usd_at_4000_referrals": round(cost_per_referral * REFERRALS_PER_MONTH, 2),
    }


def _measured_all_models():
    """REAL numbers for all 5 models in the D5(b) battery
    (results/live/model_comparison.json), each measured on the identical
    eval set. success_rate here is the D4 CODE-CHECK pass rate over all
    trials (same convention as _measured_one_model above) - not yet a
    large-sample production rate, but the best real signal available.
    variable_model_cost_per_referral divides each model's total measured
    OpenRouter cost by the UNIQUE referrals in the set (read from the
    answer key, not a hardcoded count), not by the trial count (negative
    cases get 3 trials each in the harness; production sees each
    referral once)."""
    if not os.path.exists(MODEL_COMPARISON):
        return None
    with open(MODEL_COMPARISON, encoding="utf-8") as fh:
        rows = json.load(fh)
    n_referrals = _n_referrals_in_eval_set()
    out = []
    for r in rows:
        s = r["pass_rate"]
        variable_cost = round(r["total_cost_usd"] / n_referrals, 6)
        expected_fallback = round((1 - s) * FALLBACK_COST_PER_FAILURE, 4)
        cost_per_referral = round(variable_cost + expected_fallback, 4)
        # LAYER 3 (fixed monthly - storage/infra/eval-runs/monitoring)
        # is added ONCE per month, not per referral, then folded into
        # the per-4000-referrals monthly total below.
        monthly_cost = round(cost_per_referral * REFERRALS_PER_MONTH + LAYER_3_FIXED_MONTHLY_USD, 2)
        out.append({
            "model": r["model"],
            "success_rate_measured": s,
            "negative_success_rate_measured": r.get("negative_pass_rate"),
            "mean_latency_seconds": r.get("mean_latency_seconds"),
            "variable_model_cost_per_referral_usd_MEASURED": variable_cost,
            "expected_fallback_cost_per_referral_usd": expected_fallback,
            "cost_per_referral_usd": cost_per_referral,
            "cost_per_successful_referral_usd": round(cost_per_referral / s, 4) if s else None,
            "layer_3_fixed_monthly_usd": LAYER_3_FIXED_MONTHLY_USD,
            "monthly_cost_usd_at_4000_referrals": monthly_cost,
        })
    out.sort(key=lambda x: x["monthly_cost_usd_at_4000_referrals"])
    return out


def _switch_breakeven(measured_all):
    """The break-even question D6 actually asks: 'how good would the
    CHEAP model have to be before the money it saves per run stops
    being eaten by the failures it causes?' - NOT the same question as
    d6_breakeven.json above (which asks whether automating beats no
    automation at all for one model in isolation).

    Three quantities:
      C = one run on the cheap model, TOKENS ONLY (its own failures are
          not priced in - its success rate is the unknown being solved
          for, so it cannot appear on that side of the sum)
      E = one SUCCESSFUL task on the expensive model (its own layer 1 +
          layer 2, since its success rate IS measured)
      F = one failure's cost (the fallback figure)

    failures_affordable = (E - C) / F
    breakeven_success_rate = 1 - failures_affordable

    Chosen pairing, from this project's own D5(b) measured data:
    E = openai/gpt-4o-mini (the best-performing model in the battery -
    100% measured success, so ALL of its cost is layer 1, zero layer 2);
    C = mistralai/mistral-nemo (the cheapest raw per-token price in the
    battery). This is the pairing an operator would actually face:
    "the model I'd otherwise ship" vs "the cheapest alternative on the
    table" - not an arbitrary two models."""
    by_model = {m["model"]: m for m in measured_all}
    expensive = by_model.get("openai/gpt-4o-mini")
    cheap = by_model.get("mistralai/mistral-nemo")
    if not expensive or not cheap:
        return None
    E = expensive["cost_per_referral_usd"]  # layer1+layer2 already folded in above
    C = cheap["variable_model_cost_per_referral_usd_MEASURED"]  # tokens only
    F = FALLBACK_COST_PER_FAILURE
    failures_affordable = (E - C) / F
    breakeven = round(1 - failures_affordable, 6)
    return {
        "definition": "The success rate the CHEAP model needs before switching to "
                      "it stops paying for itself. failures_affordable = (E-C)/F; "
                      "breakeven_success_rate = 1 - failures_affordable.",
        "expensive_model": expensive["model"],
        "E_cost_per_successful_task_usd": E,
        "cheap_model": cheap["model"],
        "C_cost_per_run_tokens_only_usd": C,
        "F_failure_cost_usd": F,
        "E_minus_C_usd": round(E - C, 6),
        "failures_affordable_fraction": round(failures_affordable, 6),
        "breakeven_success_rate": breakeven,
        "cheap_model_measured_success_rate": cheap["success_rate_measured"],
        "cheap_model_clears_breakeven": cheap["success_rate_measured"] >= breakeven,
        "interpretation": (
            "%s costs $%.6f per SUCCESSFUL referral outright (it is already "
            "cheap AND accurate: %.1f%% measured success, so layer 2 is "
            "effectively zero). %s's own tokens cost only $%.6f per run - "
            "cheaper still - but for switching to it to pay off, it would need "
            "to succeed %.2f%% of the time. It is measured at %.1f%%, nowhere "
            "close. This is Class 4's own worked-example insight in its most "
            "extreme form: when the reference option is ALREADY this cheap and "
            "this accurate, no amount of additional per-token savings from a "
            "worse model can close the gap - a %s failure costs $%.2f, and "
            "that number, not the sticker price, decides which model ships."
            % (expensive["model"], E, expensive["success_rate_measured"] * 100,
               cheap["model"], C, breakeven * 100,
               cheap["success_rate_measured"] * 100, "Problem B", F)),
    }


def _real_sensitivity(measured_all):
    """Sensitivity around each model's OWN measured success rate, +-10
    percentage points (clamped to [0,1]) - using REAL D5(b) data, not
    the illustrative scripted-estimate sweep below."""
    out = []
    for m in measured_all:
        base = m["success_rate_measured"]
        variable = m["variable_model_cost_per_referral_usd_MEASURED"]
        points = []
        for s in (max(0.0, base - 0.10), base, min(1.0, base + 0.10)):
            expected_fallback = round((1 - s) * FALLBACK_COST_PER_FAILURE, 4)
            cost_per_referral = round(variable + expected_fallback, 4)
            monthly = round(cost_per_referral * REFERRALS_PER_MONTH + LAYER_3_FIXED_MONTHLY_USD, 2)
            points.append({"success_rate": round(s, 4), "cost_per_referral_usd": cost_per_referral,
                           "monthly_cost_usd": monthly})
        swing = round(points[0]["monthly_cost_usd"] - points[2]["monthly_cost_usd"], 2)
        out.append({"model": m["model"], "baseline_success_rate": base, "points": points,
                    "monthly_cost_swing_usd_over_20pp": swing})
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    variable_cost_per_referral, n = _mean_estimated_cost_per_case()

    d6_inputs = {
        "MEASUREMENT_STATUS": "ESTIMATED - see module docstring. Not a live measurement.",
        "referrals_per_month": REFERRALS_PER_MONTH,
        "fallback_hourly_rate_usd": FALLBACK_RATE_USD_PER_HOUR,
        "fallback_minutes_per_failure": FALLBACK_MINUTES,
        "fallback_cost_per_failure_usd": FALLBACK_COST_PER_FAILURE,
        "variable_model_cost_per_referral_usd_ESTIMATE": variable_cost_per_referral,
        "estimate_source": "mean scripted-backend token estimate over %d cases, "
                           "priced at PRICE_IN=%.2f/PRICE_OUT=%.2f per "
                           "million tokens (config.py)"
                           % (n, config.PRICE_IN, config.PRICE_OUT),
        "illustrative_success_rates": ILLUSTRATIVE_SUCCESS_RATES,
        "baseline_success_rate_for_sensitivity": BASELINE_SUCCESS_RATE,
    }

    d6_model_costs = []
    for s in ILLUSTRATIVE_SUCCESS_RATES:
        expected_fallback = round((1 - s) * FALLBACK_COST_PER_FAILURE, 4)
        cost_per_referral = round(variable_cost_per_referral + expected_fallback, 4)
        cost_per_successful_referral = round(cost_per_referral / s, 4)
        monthly_cost = round(cost_per_referral * REFERRALS_PER_MONTH, 2)
        d6_model_costs.append({
            "success_rate": s,
            "variable_model_cost_per_referral_usd": variable_cost_per_referral,
            "expected_fallback_cost_per_referral_usd": expected_fallback,
            "cost_per_referral_usd": cost_per_referral,
            "cost_per_successful_referral_usd": cost_per_successful_referral,
            "monthly_cost_usd": monthly_cost,
        })

    base = BASELINE_SUCCESS_RATE
    sensitivity_points = [round(base - 0.10, 2), base, round(base + 0.10, 2)]
    d6_sensitivity = []
    for s in sensitivity_points:
        s = min(max(s, 0.0), 1.0)
        expected_fallback = round((1 - s) * FALLBACK_COST_PER_FAILURE, 4)
        cost_per_referral = round(variable_cost_per_referral + expected_fallback, 4)
        monthly_cost = round(cost_per_referral * REFERRALS_PER_MONTH, 2)
        d6_sensitivity.append({
            "success_rate": s,
            "delta_from_baseline_pp": round((s - base) * 100, 1),
            "cost_per_referral_usd": cost_per_referral,
            "monthly_cost_usd": monthly_cost,
        })
    monthly_low = d6_sensitivity[0]["monthly_cost_usd"]
    monthly_high = d6_sensitivity[-1]["monthly_cost_usd"]
    d6_sensitivity_summary = {
        "baseline_success_rate": base,
        "range_tested_pp": "+/-10",
        "points": d6_sensitivity,
        "monthly_cost_swing_usd": round(monthly_low - monthly_high, 2),
        "note": "A 10-point swing in success rate around the illustrative "
                "%.0f%% baseline moves the monthly bill by US$%.2f, almost "
                "entirely through the FALLBACK term, not the model term - "
                "the fallback cost (US$%.2f/failure) dominates the variable "
                "model cost (US$%.4f/referral, estimated) at this scale."
                % (base * 100, abs(monthly_low - monthly_high),
                   FALLBACK_COST_PER_FAILURE, variable_cost_per_referral),
    }

    # break-even: the success rate at which automating costs the same,
    # per referral, as NOT automating at all (paying the fallback for
    # every single referral). Below this rate automation is a net loss.
    s_breakeven = round(variable_cost_per_referral / FALLBACK_COST_PER_FAILURE, 6)
    d6_breakeven = {
        "definition": "success rate s* at which variable_cost + (1-s*)*fallback "
                      "== fallback (i.e. automating is no better than manual "
                      "fallback for every referral). Solve: "
                      "s* = variable_cost_per_referral / fallback_cost_per_failure.",
        "variable_cost_per_referral_usd_ESTIMATE": variable_cost_per_referral,
        "fallback_cost_per_failure_usd": FALLBACK_COST_PER_FAILURE,
        "breakeven_success_rate": s_breakeven,
        "interpretation": "Below a %.2f%% success rate, this agent costs MORE "
                          "per referral than simply having a human handle every "
                          "referral by hand - automation only pays for itself "
                          "above that line. Given the ESTIMATED (not measured) "
                          "variable cost, this line itself is provisional."
                          % (s_breakeven * 100),
    }

    cost_levers = {
        "tool_block_size": "The system prompt's tool descriptors are resent on "
                           "EVERY turn (see prompt.py / prompt.audit()). A "
                           "longer descriptor block multiplies its cost by the "
                           "number of turns in every run, not just once - "
                           "measured in characters/~tokens via `run_eval.py "
                           "--prompt`.",
        "turn_count": "Each turn re-sends the growing transcript, so cost grows "
                      "roughly with T (turns) and, for the base prompt prefix, "
                      "with T again - see D2(c)'s parallel-vs-sequential result "
                      "(results/parallelism/comparison.json): grouping "
                      "independent calls into fewer turns is a direct token "
                      "saving, not just a latency one.",
        "observation_size": "Tool observations are appended to the transcript "
                            "and re-sent every subsequent turn. get_clinic_slots "
                            "can return many rows; trimming or summarising large "
                            "observations before they re-enter the transcript is "
                            "a lever this project's tools do not yet exploit.",
        "success_rate": "Dominates the fallback term (see the sensitivity note "
                        "above) once fallback cost per failure (US$%.2f) is "
                        "much larger than the per-referral model cost - true at "
                        "this dataset's scale, and the reason chasing success "
                        "rate matters more than shaving tokens once a model is "
                        "already cheap." % FALLBACK_COST_PER_FAILURE,
    }

    d6_summary = {
        "MEASUREMENT_STATUS": d6_inputs["MEASUREMENT_STATUS"],
        "referrals_per_month": REFERRALS_PER_MONTH,
        "fallback_cost_per_failure_usd": FALLBACK_COST_PER_FAILURE,
        "variable_model_cost_per_referral_usd_ESTIMATE": variable_cost_per_referral,
        "cost_by_success_rate": d6_model_costs,
        "breakeven_success_rate": s_breakeven,
        "sensitivity_pp": 10,
        "cost_levers": cost_levers,
        "next_step": "Re-run this script unchanged once "
                    "results/live/model_comparison.json exists (D5b) - swap "
                    "the ESTIMATE line for the measured mean cost and the "
                    "ILLUSTRATIVE success rates for the measured pass rate.",
    }

    with open(os.path.join(OUT_DIR, "d6_inputs.json"), "w", encoding="utf-8") as fh:
        json.dump(d6_inputs, fh, indent=2)
    with open(os.path.join(OUT_DIR, "d6_model_costs.json"), "w", encoding="utf-8") as fh:
        json.dump(d6_model_costs, fh, indent=2)
    with open(os.path.join(OUT_DIR, "d6_sensitivity.json"), "w", encoding="utf-8") as fh:
        json.dump(d6_sensitivity_summary, fh, indent=2)
    with open(os.path.join(OUT_DIR, "d6_breakeven.json"), "w", encoding="utf-8") as fh:
        json.dump(d6_breakeven, fh, indent=2)
    measured = _measured_one_model()
    if measured:
        d6_summary["measured_one_model"] = measured
        with open(os.path.join(OUT_DIR, "d6_measured_live.json"), "w", encoding="utf-8") as fh:
            json.dump(measured, fh, indent=2)

    measured_all = _measured_all_models()
    if measured_all:
        cheapest = measured_all[0]
        n_referrals = _n_referrals_in_eval_set()
        d6_summary["measured_all_models"] = measured_all
        d6_summary["measured_all_models_note"] = (
            "5-model D5(b) battery, all on the identical %d-case v2-prompt "
            "eval set, real OpenRouter usage. Cheapest at this "
            "scale (4000 referrals/month) is %s at $%.2f/month, driven "
            "almost entirely by its %.1f%% success rate keeping the "
            "fallback term small - not by having the lowest raw per-token "
            "price. A model with a lower sticker price but a materially "
            "lower success rate (e.g. mistralai/mistral-nemo or "
            "meta-llama/llama-3.1-8b-instruct, both <40%% pass) costs far "
            "more overall once the $%.2f/failure fallback is priced in."
            % (n_referrals, cheapest["model"], cheapest["monthly_cost_usd_at_4000_referrals"],
               cheapest["success_rate_measured"] * 100, FALLBACK_COST_PER_FAILURE))
        with open(os.path.join(OUT_DIR, "d6_measured_all_models.json"), "w", encoding="utf-8") as fh:
            json.dump(measured_all, fh, indent=2)

        switch_breakeven = _switch_breakeven(measured_all)
        if switch_breakeven:
            d6_summary["switch_breakeven"] = switch_breakeven
            with open(os.path.join(OUT_DIR, "d6_switch_breakeven.json"), "w", encoding="utf-8") as fh:
                json.dump(switch_breakeven, fh, indent=2)
            print("\n" + "=" * 68)
            print("Switch break-even: cheap model vs expensive model")
            print("=" * 68)
            print(json.dumps(switch_breakeven, indent=2))

        real_sensitivity = _real_sensitivity(measured_all)
        d6_summary["real_sensitivity_per_model"] = real_sensitivity
        with open(os.path.join(OUT_DIR, "d6_real_sensitivity.json"), "w", encoding="utf-8") as fh:
            json.dump(real_sensitivity, fh, indent=2)

    with open(os.path.join(OUT_DIR, "d6_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(d6_summary, fh, indent=2)

    print(json.dumps(d6_summary, indent=2))
    print("\nWrote d6_inputs.json, d6_model_costs.json, d6_sensitivity.json, "
          "d6_breakeven.json, d6_summary.json"
          + (", d6_measured_live.json" if measured else "")
          + (", d6_measured_all_models.json, d6_switch_breakeven.json, "
             "d6_real_sensitivity.json" if measured_all else "") + " to", OUT_DIR)


if __name__ == "__main__":
    main()
