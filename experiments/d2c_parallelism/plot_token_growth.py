#!/usr/bin/env python3
"""
D2(c) / D6 SUPPORTING PLOT - input tokens ~ B*T + D*T^2/2, ONE curve per
live model, fit from this project's own real D5(b) data (results/live/).
====================================================================
B (base prefix, re-sent every turn) and D (tokens added per turn) are not
assumed - they are fit, per model, from that model's own real D5(b)
data, by weighted least squares on

    tokens_in = B*T + (D/2)*T^2

(no intercept - at T=0 no call has been made yet, so 0 tokens is exactly
right), fit against the MEAN tokens_in at each distinct turn count
(weighted by how many of the 95 trials landed there), not the raw
per-trial pairs - raw pairs mix together different REFERRAL CASES at
the same turn count (an escalate case stopping at T=2 and a book case
also stopping at T=2 do not carry the same content), so a per-trial fit
partly captures case-mix noise rather than the mechanical
prefix-regrowth effect this formula describes; binning by turn count
first removes most of that noise. This is the same formula the brief
gives (Class 4 Capsule 3 / Class 5's notebook), applied per-model
instead of illustratively.

REAL FINDING FROM THIS FIT: every model's fitted D comes out small
relative to B over the 1-7 turn range this project's cases actually
reach - growth looks close to LINEAR here, not sharply quadratic. This
is consistent with D2(b)'s compact-return-shape poka-yoke keeping each
turn's own added observation small; the quadratic term is real (see the
brief's own T=12 worked example) but only dominates at higher turn
counts than this eval set's cases reach (median 2, worst case 5-7).

`anthropic/claude-3-haiku` is excluded - it is the excluded-from-headline
0%-protocol-failure model (see docs/D5_MODEL_BATTERY.md), and its trials
are the wrong shape for this fit (it never completed a normal turn
sequence). `openai/gpt-4o-mini` has only two distinct turn values in its
95 trials (2 and 4) - noted on the plot rather than hidden, since a
2-point fit is exact but not a real regression.
====================================================================
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE_DIR = os.path.join(HERE, "..", "..", "results", "live")
OUT_DIR = os.path.join(HERE, "..", "..", "results", "live")

EXCLUDE = {"anthropic/claude-3-haiku"}

# Okabe-Ito categorical palette - colorblind-safe, fixed assignment order
# (never re-cycled per model; same order used in docs/D5_MODEL_BATTERY.md's
# own model listing: gpt-4o-mini, gemini-flash-lite, qwen, llama, mistral-nemo).
COLORS = {
    "openai/gpt-4o-mini": "#0072B2",
    "google/gemini-2.5-flash-lite": "#E69F00",
    "qwen/qwen-2.5-72b-instruct": "#009E73",
    "meta-llama/llama-3.1-8b-instruct": "#D55E00",
    "mistralai/mistral-nemo": "#CC79A7",
}


def _load_turns_tokens(path):
    """Returns (model, binned) where binned is a list of (turns, mean_tokens_in,
    n_trials_at_this_turn_count) - one row per DISTINCT turn count, not one row
    per trial. Binning first matters: raw per-trial (turns, tokens_in) pairs mix
    together different REFERRAL CASES at each turn count (an escalate case that
    stops at T=2 and a book case that also happens to stop at T=2 do not carry
    the same content), so a per-trial regression partly fits case-mix noise
    rather than the mechanical prefix-regrowth effect the formula describes.
    The mean at each turn count is a much cleaner signal - see the fit's own
    resulting near-linearity below, which is itself a real finding (D2(b)'s
    compact return shapes appear to have kept observations small enough that
    the quadratic term barely shows up in the 1-7 turn range this project's
    cases actually reach)."""
    d = json.load(open(path, encoding="utf-8"))
    by_t = {}
    for t in d["trials"]:
        r = t["record"]
        if r.get("turns", 0) > 0:
            by_t.setdefault(r["turns"], []).append(r["tokens_in"])
    binned = [(t, sum(v) / len(v), len(v)) for t, v in sorted(by_t.items())]
    return d["summary"]["model"], binned


def _fit_b_d(binned):
    """Weighted least squares fit of tokens_in = B*T + (D/2)*T^2, no
    intercept, over the BINNED (turns, mean_tokens_in) points - each
    weighted by how many real trials landed at that turn count."""
    sx2 = sum(w * t * t for t, _, w in binned)
    sx3 = sum(w * t ** 3 for t, _, w in binned)
    sx4 = sum(w * t ** 4 for t, _, w in binned)
    sy1 = sum(w * tok * t for t, tok, w in binned)
    sy2 = sum(w * tok * (t * t) for t, tok, w in binned)
    a11, a12 = sx2, sx3 / 2.0
    a21, a22 = sx3, sx4 / 2.0
    det = a11 * a22 - a12 * a21
    if abs(det) < 1e-9:
        return None, None
    B = (sy1 * a22 - a12 * sy2) / det
    D = (a11 * sy2 - sy1 * a21) / det
    return B, D


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    fits = {}
    for path in sorted(glob.glob(os.path.join(LIVE_DIR, "*.json"))):
        if "comparison" in path or "token_growth_fits" in path:
            continue
        model, binned = _load_turns_tokens(path)
        if model in EXCLUDE or not binned:
            continue
        B, D = _fit_b_d(binned)
        n_trials = sum(w for _, _, w in binned)
        fits[model] = {"B": B, "D": D, "binned": binned, "n_trials": n_trials}
        print("%-35s B=%7.1f  D=%7.1f  (fit from %d trials binned into %d turn "
              "counts: %s)" % (model, B, D, n_trials, len(binned),
                                [t for t, _, _ in binned]))

    with open(os.path.join(OUT_DIR, "token_growth_fits.json"), "w", encoding="utf-8") as fh:
        json.dump({m: {"B": v["B"], "D": v["D"], "n_trials": v["n_trials"],
                        "binned_turns_mean_tokens_n": v["binned"]}
                   for m, v in fits.items()}, fh, indent=2)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        sys.exit("matplotlib not installed - pip install matplotlib to render the plot "
                 "(token_growth_fits.json was still written above).")

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=150)
    T = list(range(0, 13))
    for model, v in fits.items():
        B, D = v["B"], v["D"]
        curve = [B * t + D * t * t / 2.0 for t in T]
        color = COLORS.get(model, "#666666")
        label = model.split("/")[-1]
        if len(v["binned"]) <= 2:
            label += "  (fit from only %d turn counts - illustrative)" % len(v["binned"])

        max_observed = max(t for t, _, _ in v["binned"])
        solid_T = [t for t in T if t <= max_observed]
        solid_curve = [B * t + D * t * t / 2.0 for t in solid_T]
        dashed_T = [t for t in T if t >= max_observed]
        dashed_curve = [B * t + D * t * t / 2.0 for t in dashed_T]

        ax.plot(solid_T, solid_curve, color=color, linewidth=2, label=label)
        ax.plot(dashed_T, dashed_curve, color=color, linewidth=1.3,
               linestyle=(0, (4, 3)), alpha=0.6)
        # overlay the real measured means this fit came from, sized by trial count
        obs_t = [t for t, _, _ in v["binned"]]
        obs_tok = [tok for _, tok, _ in v["binned"]]
        obs_n = [w for _, _, w in v["binned"]]
        ax.scatter(obs_t, obs_tok, color=color, s=[12 + 3 * n for n in obs_n],
                   alpha=0.6, zorder=3, edgecolors="white", linewidths=0.5)

    ax.text(0.02, 0.02,
            "Dashed = extrapolated beyond this project's observed turn range\n"
            "(max turn actually reached in the 55-case eval set is 7);\n"
            "the downturn on some dashed segments is a fit artifact of a\n"
            "small-magnitude negative D, not a real prediction.",
            transform=ax.transAxes, fontsize=7, color="#555555", va="bottom")

    ax.set_xlabel("Turns (T)")
    ax.set_ylabel("Input tokens (this run's whole re-sent transcript)")
    ax.set_title("Input tokens ~ B·T + D·T²/2, fit per model from D5(b)'s real 95-trial battery")
    ax.set_xlim(0, 12)
    ax.grid(True, linewidth=0.5, alpha=0.3)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.tight_layout()

    out_path = os.path.join(OUT_DIR, "token_growth_all_models.png")
    fig.savefig(out_path)
    print("\nWrote", out_path)
    print("Wrote", os.path.join(OUT_DIR, "token_growth_fits.json"))


if __name__ == "__main__":
    main()
