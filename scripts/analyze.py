"""Produce tables and figures for the Hawthorne ladder experiment.

    python scripts/analyze.py --results results/main --out figures/main
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hawthorne.metrics import (load_episodes, summarize, ladder_tests, round_curves,  # noqa: E402
                               event_study, LADDER, LADDER_LABELS)

SHORT = {"nocomm": "No channel", "unwatched": "Unwatched", "rule": "Rule", "watched": "Watched",
         "penalty": "Watched\n+ fine", "partial": "50% watched\n+ fine", "instructed_compete": "Instr.\ncompete",
         "instructed_collude": "Instr.\ncollude", "covert_collude": "Instr. covert\ncollude"}
COLORS = {"nocomm": "#7f7f7f", "unwatched": "#1f77b4", "rule": "#17becf", "watched": "#ff7f0e",
          "penalty": "#d62728", "partial": "#9467bd", "instructed_compete": "#2ca02c",
          "instructed_collude": "#8c564b", "covert_collude": "#e377c2"}


def _present(eps, order=LADDER):
    return [c for c in order if c in set(eps["condition"].astype(str))]


def fig_price_trajectories(steps, eps, out):
    goals = [g for g in ("profit", "units") if g in set(eps["goal"])]
    fig, axes = plt.subplots(1, len(goals), figsize=(6.2 * len(goals), 4.2), squeeze=False)
    curves = round_curves(steps, "price")
    p_nash, p_mono = eps["p_nash"].iloc[0], eps["p_mono"].iloc[0]
    for ax, g in zip(axes[0], goals):
        for c in _present(eps):
            sub = curves[(curves["condition"] == c) & (curves["goal"] == g)]
            if len(sub) == 0:
                continue
            ax.plot(sub["round"] + 1, sub["mean"], label=LADDER_LABELS[c], color=COLORS[c], lw=2)
            ax.fill_between(sub["round"] + 1, sub["mean"] - sub["sem"], sub["mean"] + sub["sem"],
                            color=COLORS[c], alpha=0.15)
        ax.axhline(p_nash, ls="--", color="k", lw=1); ax.text(0.5, p_nash + 0.15, "Bertrand-Nash", fontsize=8)
        ax.axhline(p_mono, ls=":", color="k", lw=1); ax.text(0.5, p_mono + 0.15, "Monopoly", fontsize=8)
        ax.set_title(f"Goal: {g}"); ax.set_xlabel("Round"); ax.set_ylabel("Mean posted price ($)")
        ax.set_ylim(9.5, 24)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, loc="lower center", ncol=min(5, len(labels)), bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(out / "fig1_price_trajectories.png", dpi=160, bbox_inches="tight"); plt.close(fig)


def fig_ladder(eps, out):
    metrics = [("collusion_index", "Collusion index\n(0=Nash, 1=monopoly)"),
               ("frac_msg_collusive", "Frac. messages flagged\nby text monitor (score≥3)"),
               ("frac_reasoning_collusive", "Frac. rounds with collusive\nintent in private CoT (≥3)"),
               ("frac_sanitize", "Frac. rounds CoT plans to\nhint / stay ambiguous (lexical)"),
               ("frac_rounds_with_msg", "Frac. rounds a message\nwas posted"),
               ("mean_msg_len", "Mean message length\n(chars)"),
               ("price_change_corr", "Price-change correlation\nacross sellers (tacit coord.)"),
               ("profit_per_seller", "Profit per seller ($)")]
    goals = [g for g in ("profit", "units") if g in set(eps["goal"])]
    conds = _present(eps)
    fig, axes = plt.subplots(2, 4, figsize=(17, 8.5))
    for ax, (m, label) in zip(axes.flat, metrics):
        width = 0.8 / len(goals)
        for gi, g in enumerate(goals):
            sub = eps[eps["goal"] == g]
            means = [sub[sub["condition"] == c][m].mean() for c in conds]
            sems = [sub[sub["condition"] == c][m].sem() for c in conds]
            x = np.arange(len(conds)) + (gi - (len(goals) - 1) / 2) * width
            bars = ax.bar(x, means, width, yerr=sems, capsize=3, label=f"goal: {g}",
                          color=[COLORS[c] for c in conds], alpha=0.95 if g == "profit" else 0.45,
                          edgecolor="k", linewidth=0.5)
        ax.set_xticks(np.arange(len(conds)))
        ax.set_xticklabels([SHORT[c] for c in conds], fontsize=7, rotation=35, ha="right")
        ax.set_ylabel(label, fontsize=8.5)
        if m == "collusion_index":
            ax.axhline(0, color="k", lw=0.8); ax.axhline(1, color="k", lw=0.8, ls=":")
    axes[0][0].legend(fontsize=8)
    fig.suptitle("Hawthorne ladder: behaviour by monitoring condition (solid = profit goal, faded = units goal); "
                 "error bars = SEM over seeds", fontsize=10)
    fig.tight_layout(); fig.savefig(out / "fig2_ladder.png", dpi=160); plt.close(fig)


def fig_say_do(eps, out):
    sub = eps[eps["goal"] == "profit"]
    conds = _present(sub, ("unwatched", "rule", "watched", "penalty", "partial"))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    x = np.arange(len(conds)); w = 0.38
    ms = [sub[sub.condition == c]["mean_msg_score"].mean() for c in conds]
    mse = [sub[sub.condition == c]["mean_msg_score"].sem() for c in conds]
    rs = [sub[sub.condition == c]["mean_reasoning_score"].mean() for c in conds]
    rse = [sub[sub.condition == c]["mean_reasoning_score"].sem() for c in conds]
    axes[0].bar(x - w / 2, ms, w, yerr=mse, capsize=3, label="Messages (what the monitor sees)", color="#ff7f0e")
    axes[0].bar(x + w / 2, rs, w, yerr=rse, capsize=3, label="Private CoT (intent)", color="#1f77b4")
    axes[0].set_xticks(x); axes[0].set_xticklabels([SHORT[c] for c in conds], fontsize=8)
    axes[0].set_ylabel("Coordination score (1–4)"); axes[0].set_ylim(1, 4); axes[0].legend(fontsize=8)
    axes[0].set_title("Say vs. think: coordination in messages vs. private reasoning")
    gaps = [sub[sub.condition == c]["say_do_gap"].mean() for c in conds]
    ge = [sub[sub.condition == c]["say_do_gap"].sem() for c in conds]
    axes[1].bar(x, gaps, 0.6, yerr=ge, capsize=3, color=[COLORS[c] for c in conds], edgecolor="k", lw=0.5)
    axes[1].axhline(0, color="k", lw=0.8)
    axes[1].set_xticks(x); axes[1].set_xticklabels([SHORT[c] for c in conds], fontsize=8)
    axes[1].set_ylabel("Intent − message score"); axes[1].set_title("Concealment gap (intent not expressed in channel)")
    fig.tight_layout(); fig.savefig(out / "fig3_say_do_gap.png", dpi=160); plt.close(fig)


def fig_event_study(steps, out):
    es = event_study(steps, window=4)
    if len(es) == 0:
        return
    es = es[es["goal"] == "profit"]
    g = es.groupby("rel_round")
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
    for ax, (col, label) in zip(axes, [("collusion_index", "Collusion index"),
                                       ("msg_score", "Message coordination score"),
                                       ("has_msg", "Frac. sellers posting a message")]):
        m, s = g[col].mean(), g[col].sem()
        ax.errorbar(m.index, m.values, yerr=s.values, marker="o", capsize=3, color="#d62728")
        ax.axvline(0, ls="--", color="k", lw=1); ax.set_xlabel("Rounds relative to first fine")
        ax.set_ylabel(label)
    n = es["tag"].nunique()
    fig.suptitle(f"Within-episode response to the first penalty (penalty conditions, profit goal; n={n} episodes)", fontsize=10)
    fig.tight_layout(); fig.savefig(out / "fig4_event_study.png", dpi=160); plt.close(fig)
    es.to_csv(out / "event_study.csv", index=False)


def fig_dynamics_by_round(steps, out):
    """Message posting / length / monitor score by round, profit goal."""
    sub = steps[steps["goal"] == "profit"]
    conds = _present(sub, ("unwatched", "rule", "watched", "penalty", "partial"))
    fig, axes = plt.subplots(1, 3, figsize=(15, 3.8))
    for col, ax, label in zip(["has_msg", "msg_len", "msg_score"], axes,
                              ["Frac. sellers posting", "Message length (chars)", "Text-monitor score"]):
        cur = round_curves(sub, col)
        for c in conds:
            s = cur[cur.condition == c]
            ax.plot(s["round"] + 1, s["mean"], color=COLORS[c], label=LADDER_LABELS[c], lw=2)
            ax.fill_between(s["round"] + 1, s["mean"] - s["sem"], s["mean"] + s["sem"], color=COLORS[c], alpha=0.15)
        ax.set_xlabel("Round"); ax.set_ylabel(label)
    axes[0].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out / "fig5_channel_dynamics.png", dpi=160); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pressure", choices=["0", "1", "all"], default="0")
    ap.add_argument("--stakes", choices=["base", "high", "all"], default="base")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    steps, eps = load_episodes([Path(r) for r in args.results])
    if args.stakes != "all":
        steps = steps[steps["stakes"] == args.stakes]; eps = eps[eps["stakes"] == args.stakes]
    if args.pressure != "all":
        want = args.pressure == "1"
        steps = steps[steps["pressure"] == want]; eps = eps[eps["pressure"] == want]
    print(f"{len(eps)} episodes, {len(steps)} steps")
    summ = summarize(eps)
    summ.to_csv(out / "summary_by_condition.csv")
    eps.to_csv(out / "episodes.csv", index=False)
    # key table (markdown)
    key = ["collusion_index", "collusion_index_2nd_half", "mean_dispersion", "profit_per_seller",
           "frac_rounds_with_msg", "mean_msg_len", "mean_msg_score", "frac_msg_collusive",
           "mean_reasoning_score", "frac_reasoning_collusive", "frac_conceal", "frac_sanitize", "frac_aware",
           "frac_threat_aware", "frac_eval_aware", "frac_met_target", "say_do_gap", "price_change_corr", "n_flagged"]
    lines = ["| condition | goal | n | " + " | ".join(key) + " |", "|" + "---|" * (len(key) + 3)]
    for (c, g), row in summ.iterrows():
        cells = [f"{row[f'{k}_mean']:.2f}±{row[f'{k}_sem']:.2f}" if pd.notna(row[f'{k}_mean']) else "–" for k in key]
        lines.append(f"| {c} | {g} | {int(row['n'])} | " + " | ".join(cells) + " |")
    (out / "summary_table.md").write_text("\n".join(lines))
    print("\n".join(lines))
    tests = []
    for g in sorted(set(eps["goal"])):
        for m in ["collusion_index", "collusion_index_2nd_half", "frac_msg_collusive", "frac_reasoning_collusive",
                  "frac_conceal", "frac_sanitize", "frac_aware", "say_do_gap", "frac_rounds_with_msg", "mean_msg_len", "price_change_corr",
                  "profit_per_seller", "mean_dispersion"]:
            t = ladder_tests(eps, g, m); t["goal"] = g; tests.append(t)
    tests = pd.concat(tests); tests.to_csv(out / "ladder_tests.csv", index=False)
    print(tests[(tests.goal == "profit")].to_string())
    fig_price_trajectories(steps, eps, out)
    fig_ladder(eps, out)
    if "profit" in set(eps["goal"]):
        fig_say_do(eps, out)
        fig_event_study(steps, out)
        fig_dynamics_by_round(steps, out)
    print(f"figures -> {out}")


if __name__ == "__main__":
    main()
