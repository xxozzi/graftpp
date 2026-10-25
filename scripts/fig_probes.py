"""Probe figures: (a) three evidence streams by condition, (b) detection of covert collusion by monitor type,
(c) probe score over rounds in the penalty condition around fines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ORDER = ["nocomm", "unwatched", "rule", "watched", "penalty", "partial"]
SHORT = {"nocomm": "No channel", "unwatched": "Unwatched", "rule": "Rule", "watched": "Watched",
         "penalty": "Watched\n+ fine", "partial": "50% watched\n+ fine"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acts-dir", default="data/main")
    ap.add_argument("--layer", type=int, default=32)
    ap.add_argument("--out", default="figures/probes")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    s = pd.read_csv(Path(args.acts_dir) / "probe_scores.csv")
    rep = json.load(open(Path(args.acts_dir) / "probe_report.json"))
    L = args.layer
    col = f"coll_natural_think_{L}"
    s["text_flag"] = (s["msg_score"].fillna(1) >= 3).astype(float)
    s["cot_flag"] = (s["reasoning_score"].fillna(1) >= 3).astype(float)
    s["probe_flag"] = (s[col] >= 0.5).astype(float)
    s["probe_flag_full"] = (s[f"{col}_fullfit"] >= 0.5).astype(float)
    nat = s[s.condition.isin(ORDER) & (~s.distilled) & (s.src_condition == s.condition) & (s.goal == "profit")]

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.2), gridspec_kw={"width_ratios": [1.5, 1, 1.1]})
    # (a) three evidence streams by condition (no pressure), per-episode mean then SEM over episodes
    ax = axes[0]
    sub = nat[~nat.pressure]
    conds = [c for c in ORDER if c in set(sub.condition)]
    per_ep = sub.groupby(["condition", "tag"], observed=True)[["text_flag", "cot_flag", "probe_flag"]].mean().reset_index()
    w = 0.26
    for i, (m, lab, c) in enumerate([("text_flag", "Text monitor (messages)", "#ff7f0e"),
                                     ("cot_flag", "CoT judge (private reasoning)", "#1f77b4"),
                                     ("probe_flag", f"Activation probe (layer {L}, out-of-fold)", "#2ca02c")]):
        means = [per_ep[per_ep.condition == k][m].mean() for k in conds]
        sems = [per_ep[per_ep.condition == k][m].sem() for k in conds]
        ax.bar(np.arange(len(conds)) + (i - 1) * w, means, w, yerr=sems, capsize=2, label=lab, color=c, edgecolor="k", lw=0.4)
    ax.set_xticks(np.arange(len(conds))); ax.set_xticklabels([SHORT[k] for k in conds], fontsize=8)
    ax.set_ylabel("Fraction of rounds flagged (score ≥3 / p ≥ 0.5)"); ax.legend(fontsize=8)
    ax.set_title("(a) Three evidence streams agree: watching ends intent, not just talk", fontsize=9.5)

    # (b) detection on covert vs overt instructed collusion (original prompts)
    ax = axes[1]
    rows = []
    for src, lab in [("instructed_collude", "Overt\n(instructed)"), ("covert_collude", "Covert\n(instructed to evade)")]:
        g = s[(s.src_condition == src) & (~s.distilled)]
        rows.append((lab, g.text_flag.mean(), g.cot_flag.mean(), g.probe_flag_full.mean()))
    x = np.arange(len(rows))
    for i, (lab, c) in enumerate([("Text monitor", "#ff7f0e"), ("CoT judge", "#1f77b4"), ("Activation probe", "#2ca02c")]):
        ax.bar(x + (i - 1) * w, [r[i + 1] for r in rows], w, label=lab, color=c, edgecolor="k", lw=0.4)
    ax.set_xticks(x); ax.set_xticklabels([r[0] for r in rows], fontsize=8); ax.set_ylim(0, 1.05)
    ax.set_ylabel("Fraction of steps flagged"); ax.legend(fontsize=8)
    ax.set_title("(b) Covert collusion: text monitor blind,\nprobe sees it (probe never trained on these)", fontsize=9.5)

    # (c) probe score distribution: natural clean vs natural intent vs covert vs overt
    ax = axes[2]
    groups = [("Natural, CoT clean", nat[nat.cot_flag == 0][col].dropna(), "#7f7f7f"),
              ("Natural, CoT intent", nat[nat.cot_flag == 1][col].dropna(), "#1f77b4"),
              ("Covert collusion", s[(s.src_condition == "covert_collude") & (~s.distilled)][f"{col}_fullfit"].dropna(), "#e377c2"),
              ("Overt collusion", s[(s.src_condition == "instructed_collude") & (~s.distilled)][f"{col}_fullfit"].dropna(), "#8c564b")]
    for i, (lab, v, c) in enumerate(groups):
        ax.hist(v, bins=25, range=(0, 1), density=True, alpha=0.55, color=c, label=f"{lab} (n={len(v)})")
    ax.axvline(0.5, color="k", ls="--", lw=1); ax.set_xlabel(f"Probe p(collusive intent), layer {L} <think> mean")
    ax.set_ylabel("density"); ax.legend(fontsize=7.5)
    auroc = rep["natural_lr"].get(f"think_{L}__intent_oof_auroc", float("nan"))
    cov_auroc = rep["natural_lr"].get(f"think_{L}__covert_vs_clean_auroc", float("nan"))
    ax.set_title(f"(c) Probe scores. OOF AUROC vs CoT judge = {auroc:.2f};\ncovert vs clean AUROC = {cov_auroc:.2f}", fontsize=9.5)
    fig.tight_layout(); fig.savefig(out / "fig_probes.png", dpi=160); plt.close(fig)

    # summary table
    tab = {"by_condition": per_ep.groupby("condition", observed=True)[["text_flag", "cot_flag", "probe_flag"]].mean().round(3).to_dict("index"),
           "instructed": {r[0].replace("\n", " "): {"text": r[1], "cot": r[2], "probe": r[3]} for r in rows},
           "oof_auroc": auroc, "covert_vs_clean_auroc": cov_auroc}
    json.dump(tab, open(out / "probe_summary.json", "w"), indent=1)
    print(json.dumps(tab, indent=1))


if __name__ == "__main__":
    main()
