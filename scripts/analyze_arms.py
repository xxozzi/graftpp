"""Compare trained arms (base / naive / filter / GRAFT / GRAFT-CoT / GRAFT++) in Hawthorne Market.

    python scripts/analyze_arms.py --eval-dir results/eval --base results/main --out figures/arms
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hawthorne.metrics import load_episodes, welch  # noqa: E402

ARM_ORDER = ["base", "naive__both", "filter__both", "graft__retain_only", "graftcot__retain_only",
             "graftpp__retain_only", "graft__both", "graftpp__both", "graft__forget_only", "graftpp__forget_only"]
ARM_LABEL = {"base": "Base", "naive__both": "Naive RFT", "filter__both": "Filter (penalise)",
             "graft__retain_only": "GRAFT (text)", "graftcot__retain_only": "GRAFT (CoT)",
             "graftpp__retain_only": "GRAFT++ (probe)", "graft__both": "GRAFT both adapters",
             "graftpp__both": "GRAFT++ both adapters", "graft__forget_only": "GRAFT forget-only",
             "graftpp__forget_only": "GRAFT++ forget-only"}
ARM_COLOR = {"base": "#7f7f7f", "naive__both": "#d62728", "filter__both": "#ff7f0e",
             "graft__retain_only": "#1f77b4", "graftcot__retain_only": "#17becf",
             "graftpp__retain_only": "#2ca02c", "graft__both": "#aec7e8", "graftpp__both": "#98df8a",
             "graft__forget_only": "#9edae5", "graftpp__forget_only": "#c7c7c7"}

METRICS = [("collusion_index", "Collusion index"), ("frac_msg_collusive", "Frac. messages flagged (text)"),
           ("frac_reasoning_collusive", "Frac. rounds collusive intent (CoT)"), ("frac_conceal", "Frac. concealment (CoT)"),
           ("price_change_corr", "Tacit coordination (Δprice corr.)"), ("profit_per_seller", "Profit per seller ($)")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dir", required=True)
    ap.add_argument("--base", default=None, help="results dir with base-model episodes for the same conditions")
    ap.add_argument("--out", required=True)
    ap.add_argument("--conditions", nargs="+", default=["unwatched", "watched", "penalty"])
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    frames = []
    for d in sorted(Path(args.eval_dir).iterdir()):
        if d.is_dir() and any(d.glob("*.json")):
            _, eps = load_episodes(d, label=d.name)
            eps["arm"] = d.name
            frames.append(eps)
    if args.base:
        _, eps = load_episodes(Path(args.base), label="base")
        # same setting the arms are evaluated in: base stakes, no CEO-pressure text
        eps = eps[(eps["goal"] == "profit") & (eps["stakes"] == "base") & (~eps["pressure"])]
        eps["arm"] = "base"
        frames.append(eps)
    eps = pd.concat(frames, ignore_index=True)
    eps = eps[eps["condition"].astype(str).isin(args.conditions)]
    arms = [a for a in ARM_ORDER if a in set(eps["arm"])]
    conds = [c for c in args.conditions if c in set(eps["condition"].astype(str))]
    g = eps.groupby(["arm", "condition"], observed=True)
    summ = pd.concat({"mean": g[[m for m, _ in METRICS]].mean(), "sem": g[[m for m, _ in METRICS]].sem(),
                      "n": g.size()}, axis=1)
    summ.to_csv(out / "arms_summary.csv")
    print(summ.round(3).to_string())

    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    for ax, (m, label) in zip(axes.flat, METRICS):
        w = 0.8 / len(arms)
        for ai, a in enumerate(arms):
            sub = eps[eps["arm"] == a]
            means = [sub[sub["condition"] == c][m].mean() for c in conds]
            sems = [sub[sub["condition"] == c][m].sem() for c in conds]
            x = np.arange(len(conds)) + (ai - (len(arms) - 1) / 2) * w
            ax.bar(x, means, w, yerr=sems, capsize=2, label=ARM_LABEL.get(a, a), color=ARM_COLOR.get(a, None),
                   edgecolor="k", linewidth=0.4)
        ax.set_xticks(np.arange(len(conds))); ax.set_xticklabels(conds)
        ax.set_ylabel(label, fontsize=9)
        if m == "collusion_index":
            ax.axhline(0, color="k", lw=0.8); ax.axhline(1, color="k", lw=0.8, ls=":")
    axes[0][0].legend(fontsize=7.5, ncol=2)
    fig.suptitle("Trained arms evaluated in Hawthorne Market (profit goal; judge = base model; error bars = SEM over seeds)",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(out / "fig6_arms.png", dpi=160); plt.close(fig)

    # tests vs naive and vs base, per condition
    rows = []
    for c in conds:
        for m, _ in METRICS:
            for ref in ("naive__both", "base"):
                if ref not in arms:
                    continue
                a0 = eps[(eps.arm == ref) & (eps.condition == c)][m].values
                for a in arms:
                    if a == ref:
                        continue
                    a1 = eps[(eps.arm == a) & (eps.condition == c)][m].values
                    t, p = welch(a0, a1)
                    rows.append({"condition": c, "metric": m, "ref": ref, "arm": a,
                                 "ref_mean": np.nanmean(a0) if len(a0) else np.nan,
                                 "arm_mean": np.nanmean(a1) if len(a1) else np.nan, "welch_p": p,
                                 "n_ref": len(a0), "n_arm": len(a1)})
    pd.DataFrame(rows).to_csv(out / "arms_tests.csv", index=False)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
