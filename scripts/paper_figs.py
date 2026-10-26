"""Figures for the paper (report/paper/figs/*.pdf), in the website's visual language.

    python scripts/paper_figs.py

Data: website/src/data/story.json (written by scripts/export_site.py, the same numbers the site shows) and, for
the GRAFT arms, the evaluation logs in results/eval and results/eval_blind.  Typeface: PP Neue Montreal.
Palette: brand blue #1c2df7; condition colours validated for colour-vision deficiency (all pairs) on white.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from site_path import site_dir  # noqa: E402
sys.path.insert(0, str(ROOT))
OUT = ROOT / "report" / "paper" / "figs"
STORY = json.load(open(site_dir() / "src" / "data" / "story.json"))

FONT_DIR = ROOT / "report" / "paper" / "fonts"
for f in FONT_DIR.glob("ppneuemontreal-*.otf"):
    fm.fontManager.addfont(str(f))

BLUE = "#1c2df7"
INK = "#0b0b0b"
INK2 = "#4a4a4a"
MUTED = "#8a8a8a"
GRID = "#e8e8e5"
BASE = "#c3c2b7"
COND = {"nocomm": "#139a74", "unwatched": "#d42a2a", "watched": "#1c2df7", "penalty": "#e39b00"}
LABEL = {"nocomm": "No channel", "unwatched": "Unwatched", "watched": "Watched", "penalty": "Watched + fine",
         "rule": "Rule stated"}
RAMP = ["#9da3fa", "#5e69f8", "#1c2df7", "#0c1690"]  # ordinal, monitor score 1..4
SCORE = ["No coordination", "Vague appeal", "Coordination attempt", "Explicit price-fixing"]
FOUR = ["nocomm", "unwatched", "watched", "penalty"]
THREE = ["unwatched", "watched", "penalty"]

plt.rcParams.update({
    "font.family": "PP Neue Montreal", "font.size": 8, "axes.titlesize": 8.6, "axes.titleweight": "medium",
    "axes.titlelocation": "left", "axes.titlepad": 10, "axes.labelsize": 7.6, "axes.labelcolor": INK2,
    "axes.edgecolor": BASE, "axes.linewidth": 0.7, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 7.2,
    "ytick.labelsize": 7.2, "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 5,
    "ytick.major.pad": 4, "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 7.4, "figure.dpi": 200,
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.03, "text.color": INK,
    "lines.solid_capstyle": "round",
})
W = 5.5  # NeurIPS text width, inches


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=180)
    plt.close(fig)
    print("->", name)


def fx(v, d=2):
    return ("−" if v < 0 else "") + f"{abs(v):.{d}f}"


def pct(v):
    return f"{v * 100:.0f}%"


def rbar(ax, x, h, w, color, base=0.0, r_pt=2.2, **kw):
    """Column square at the baseline with a rounded data end (radius in points)."""
    fig = ax.figure
    fig.canvas.draw_idle()
    bb = ax.get_window_extent()
    xr = np.diff(ax.get_xlim())[0] / bb.width * fig.dpi / 72
    yr = np.diff(ax.get_ylim())[0] / bb.height * fig.dpi / 72
    rx, ry = r_pt * xr, r_pt * yr
    top = base + h
    lo, hi = (base, top) if h >= 0 else (top, base)
    if abs(h) < 1e-9:
        return
    ext = ry * 1.2
    if h >= 0:
        box = FancyBboxPatch((x - w / 2, lo - ext), w, (hi - lo) + ext, boxstyle=f"round,pad=0,rounding_size={rx}",
                             mutation_aspect=ry / rx, fc=color, ec="none", **kw)
        clip = Rectangle((x - w, base), 2 * w, (hi - lo) + ext, transform=ax.transData)
    else:
        box = FancyBboxPatch((x - w / 2, lo), w, (hi - lo) + ext, boxstyle=f"round,pad=0,rounding_size={rx}",
                             mutation_aspect=ry / rx, fc=color, ec="none", **kw)
        clip = Rectangle((x - w, lo - ext), 2 * w, (hi - lo) + ext, transform=ax.transData)
    ax.add_patch(box)
    box.set_clip_path(clip)


def rolling(a, k=5):
    a = np.asarray(a, float)
    return np.array([a[max(0, i - k + 1): i + 1].mean() for i in range(len(a))])


def end_labels(ax, items, x, min_gap):
    """items: (y, value_text, label, color). Nudge apart, draw leader lines where moved."""
    items = sorted(items, key=lambda t: -t[0])
    placed = []
    for y, *_ in items:
        py = y
        if placed and placed[-1] - py < min_gap:
            py = placed[-1] - min_gap
        placed.append(py)
    for (y, val, lab, col), py in zip(items, placed):
        if abs(py - y) > 1e-6:
            ax.plot([x + 0.6, x + 2.2], [y, py], color=BASE, lw=0.6, clip_on=False)
        ax.text(x + 2.8, py, val, va="bottom", ha="left", fontsize=7.8, fontweight="medium", color=INK, clip_on=False)
        ax.text(x + 2.8, py, lab, va="top", ha="left", fontsize=6.6, color=INK2, clip_on=False)


# ---------------------------------------------------------------- 1. trajectories (the headline)
def fig_traj():
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.6), sharey=True, gridspec_kw={"wspace": 0.36})
    for ax, (k, title) in zip(axes, [("duo", "a   Untrained Qwen3-14B, two sellers"),
                                     ("trio", "b   Fine-tuned (naive RFT), three sellers")]):
        tr = STORY[k]["traj"]
        ends = []
        for c in FOUR:
            pts = np.array(tr[c])
            r, m, se = pts[:, 0] + 1, rolling(pts[:, 1]), rolling(pts[:, 2])
            ax.fill_between(r, m - se, m + se, color=COND[c], alpha=0.1, lw=0)
            ax.plot(r, m, color=COND[c], lw=1.5)
            ax.scatter([r[-1]], [m[-1]], s=16, color=COND[c], zorder=5, edgecolors="white", linewidths=1)
            ends.append((m[-1], fx(m[-1]), LABEL[c], COND[c]))
        for y in (0, 1):
            ax.axhline(y, color=BASE, lw=0.7, zorder=1)
        ax.set_title(title)
        ax.set_xlim(1, 100)
        ax.set_ylim(-0.38, 1.22)
        ax.set_yticks([0, 0.5, 1])
        ax.set_yticklabels(["0  competitive", "0.5", "1  monopoly"])
        ax.set_xticks([1, 25, 50, 75, 100])
        ax.set_xlabel("Round")
        end_labels(ax, ends, 100, 0.17)
    save(fig, "traj")


# ---------------------------------------------------------------- 2. say / think / do
def fig_say_think_do():
    fig, axes = plt.subplots(2, 3, figsize=(W, 3.3), gridspec_kw={"hspace": 0.62, "wspace": 0.28})
    panels = [("delta2", "Do · collusion index, 2nd half", (-0.32, 1.12), [0, 0.5, 1], fx),
              ("msgFlag", "Say · messages flagged", (0, 1.12), [0, 0.5, 1], pct),
              ("cotIntent", "Think · intent in reasoning", (0, 1.12), [0, 0.5, 1], pct)]
    for row, (k, rl) in enumerate([("duo", "Untrained, two sellers"), ("trio", "Fine-tuned, three sellers")]):
        sm = STORY[k]["summary"]
        for col, (key, title, lim, ticks, f) in enumerate(panels):
            ax = axes[row, col]
            ax.set_ylim(*lim)
            ax.set_xlim(-0.6, 3.6)
            ax.set_yticks(ticks)
            ax.set_yticklabels([f(t) if f is pct else ("0" if t == 0 else f"{t:g}") for t in ticks])
            for i, c in enumerate(FOUR):
                v = sm[c][key]
                rbar(ax, i, v, 0.42, COND[c])
                ax.text(i, v + (0.04 if v >= 0 else -0.06), f(v), ha="center", va="bottom" if v >= 0 else "top",
                        fontsize=7, color=INK, fontweight="medium")
            ax.axhline(0, color=BASE, lw=0.7)
            ax.set_xticks([])
            ax.set_title(title, fontsize=7.6, color=INK2, fontweight="normal")
        axes[row, 0].annotate(rl, xy=(0, 1.3), xycoords="axes fraction", fontsize=8.6, fontweight="medium",
                              color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COND[c]) for c in FOUR]
    fig.legend(handles, [LABEL[c] for c in FOUR], loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.05),
               handlelength=0.9, columnspacing=1.8)
    save(fig, "say_think_do")


# ---------------------------------------------------------------- 3. how explicit were the messages
def fig_explicit():
    fig, axes = plt.subplots(1, 2, figsize=(W, 1.55), sharey=True, gridspec_kw={"wspace": 0.08})
    for ax, (k, title) in zip(axes, [("duo", "Untrained, two sellers"), ("trio", "Fine-tuned, three sellers")]):
        d = STORY["msgScores"][k]
        for i, c in enumerate(THREE):
            sc = np.array(d[c]["scores"], float)
            tot = sc.sum()
            left = 0
            for j in range(4):
                wv = sc[j] / tot
                if wv > 0:
                    ax.barh(i, wv, left=left, height=0.56, color=RAMP[j], edgecolor="white", linewidth=1.2)
                    if wv > 0.09:
                        ax.text(left + wv / 2, i, pct(wv), ha="center", va="center", fontsize=6.6,
                                color="white" if j >= 1 else INK)
                left += wv
        ax.set_yticks(range(3))
        ax.set_yticklabels([LABEL[c] for c in THREE], color=INK, fontsize=7.2)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.5, 1])
        ax.set_xticklabels(["0", "50%", "100%"])
        ax.grid(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_title(title)
    axes[0].invert_yaxis()
    axes[1].set_xticklabels(["", "50%", "100%"])
    handles = [plt.Rectangle((0, 0), 1, 1, color=RAMP[j]) for j in range(4)]
    fig.legend(handles, [f"{j + 1}  {SCORE[j]}" for j in range(4)], loc="lower center", ncol=4,
               bbox_to_anchor=(0.5, -0.16), handlelength=0.9, columnspacing=1.6)
    save(fig, "explicit")


# ---------------------------------------------------------------- 4. the units-sold control
def fig_control():
    fig, axes = plt.subplots(1, 2, figsize=(W, 1.95), gridspec_kw={"wspace": 0.25})
    for ax, (key, title) in zip(axes, [("sanitize", "Reasoning plans to stay vague"), ("msgRate", "Rounds with a message")]):
        ax.set_ylim(0, 0.75)
        ax.set_xlim(-0.6, 6.6)
        for g, (src, gl) in enumerate([("base", "Profit goal"), ("units", "Units-sold goal")]):
            sm = STORY[src]["summary"]
            for i, c in enumerate(THREE):
                x = g * 4 + i
                v = sm[c][key]
                rbar(ax, x, v, 0.58, COND[c])
                ax.text(x, v + 0.025, pct(v), ha="center", va="bottom", fontsize=7, fontweight="medium")
            ax.text(g * 4 + 1, -0.17, gl, ha="center", fontsize=7.4, color=INK, transform=ax.transData)
        ax.set_xticks([0, 1, 2, 4, 5, 6])
        ax.set_xticklabels(["Unw.", "Watch.", "+ fine"] * 2, fontsize=6.4)
        ax.set_yticks([0, 0.25, 0.5])
        ax.set_yticklabels(["0", "25%", "50%"])
        ax.axhline(0, color=BASE, lw=0.7)
        ax.set_title(title)
    save(fig, "control")


# ---------------------------------------------------------------- 4b. profit goal vs units-sold goal, everything
def fig_goals():
    panels = [("delta", "Collusion index Δ", (-0.72, 0.42), [-0.5, 0, 0.25], fx),
              ("profitRound", "Profit per seller per round", (0, 1900), [0, 500, 1000, 1500], lambda v: f"${v / 1000:.1f}k" if v else "0"),
              ("msgFlag", "Messages flagged", (0, 0.45), [0, 0.2, 0.4], pct),
              ("cotIntent", "Reasoning intends to coordinate", (0, 0.45), [0, 0.2, 0.4], pct),
              ("sanitize", "Reasoning plans to stay vague", (0, 0.72), [0, 0.3, 0.6], pct),
              ("msgRate", "Rounds with a message", (0, 0.72), [0, 0.3, 0.6], pct)]
    fig, axes = plt.subplots(2, 3, figsize=(W, 3.45), gridspec_kw={"hspace": 0.62, "wspace": 0.3})
    for ax, (key, title, lim, ticks, f) in zip(axes.flat, panels):
        ax.set_ylim(*lim)
        ax.set_xlim(-0.6, 6.6)
        for g, src in enumerate(["base", "units"]):
            sm = STORY[src]["summary"]
            for i, c in enumerate(THREE):
                x = g * 4 + i
                v = sm[c][key]
                rbar(ax, x, v, 0.6, COND[c])
                if key == "delta":
                    lab = (("−" if v < 0 else "") + f"{abs(v):.2f}").replace("0.", ".")
                elif key == "profitRound":
                    lab = f"${v / 1000:.1f}k" if v >= 1000 else f"${v:.0f}"
                else:
                    lab = f(v)
                ax.text(x, v + (lim[1] - lim[0]) * (0.03 if v >= 0 else -0.05), lab, ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=5.3, fontweight="medium")
        ax.axhline(0, color=BASE, lw=0.7)
        ax.set_yticks(ticks)
        ax.set_yticklabels([f(t) if f is not fx else ("0" if t == 0 else f"{t:g}".replace("-", "−")) for t in ticks])
        ax.set_xticks([1, 5])
        ax.set_xticklabels(["Profit goal", "Units goal"], color=INK, fontsize=7)
        ax.tick_params(axis="x", pad=3)
        ax.set_title(title, fontsize=7.6)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COND[c]) for c in THREE]
    fig.legend(handles, [LABEL[c] for c in THREE], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.06),
               handlelength=0.9, columnspacing=1.8)
    save(fig, "goals")


# ---------------------------------------------------------------- 5. pressure: high stakes and steering
def fig_pressure():
    fig = plt.figure(figsize=(W, 2.3))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 2.3], wspace=0.18)
    ax = fig.add_subplot(gs[0])
    ax.set_ylim(-0.05, 0.62)
    ax.set_xlim(-0.6, 8.6)
    for g, (src, gl) in enumerate([("base", "Baseline"), ("high", "High stakes")]):
        sm = STORY[src]["summary"]
        for i, c in enumerate(FOUR):
            x = g * 5 + i
            v = sm[c]["delta"]
            rbar(ax, x, v, 0.62, COND[c])
        ax.text(g * 5 + 1.5, -0.13, gl, ha="center", fontsize=7.2, transform=ax.transData)
    ax.set_xticks([])
    ax.set_yticks([0, 0.25, 0.5])
    ax.axhline(0, color=BASE, lw=0.7)
    ax.set_title("a   Δ, whole game")

    ax = fig.add_subplot(gs[1])
    arms = [("unsteered", "No steering"), ("desperation", "Desperation"), ("realness", "Realness"),
            ("genuineness", "Genuineness"), ("naive", "Fine-tuned")]
    ax.set_ylim(-0.1, 0.78)
    ax.set_xlim(-0.6, 5 * 5 - 1.4)
    for g, (k, gl) in enumerate(arms):
        sm = STORY["testbed"][k]["summary"]
        for i, c in enumerate(FOUR):
            x = g * 5 + i
            v = sm[c]["delta2"]
            rbar(ax, x, v, 0.62, COND[c])
        ax.text(g * 5 + 1.5, -0.2, gl, ha="center", fontsize=7.2, transform=ax.transData)
        fines = sm["penalty"]["fines"]
        ax.text(g * 5 + 3, sm["penalty"]["delta2"] + 0.03, f"{fines:.0f}\nfines" if fines >= 1 else f"{fines:.1f}\nfines",
                ha="center", va="bottom", fontsize=5.8, color=INK2, linespacing=0.95)
    ax.set_xticks([])
    ax.set_yticks([0, 0.25, 0.5, 0.75])
    ax.axhline(0, color=BASE, lw=0.7)
    ax.set_title("b   Collusive testbed: Δ, 2nd half, by what drives the agents")
    handles = [plt.Rectangle((0, 0), 1, 1, color=COND[c]) for c in FOUR]
    fig.legend(handles, [LABEL[c] for c in FOUR], loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.13),
               handlelength=0.9, columnspacing=1.8)
    save(fig, "pressure")


# 6. the probe: scripts/probe_analysis.py writes figs/probe.pdf (detectors, baselines, controls)


# ---------------------------------------------------------------- 7. the dilemma (method)
def fig_dilemma():
    from hawthorne.market import MarketParams, profits
    mp = MarketParams(n_sellers=3)
    p = np.linspace(10, 26, 400)
    fig, ax = plt.subplots(figsize=(3.1, 2.15))
    for rival, col, lab in [(13.70, RAMP[0], "rivals at $13.70"), (17.0, RAMP[1], "rivals at $17"), (20.0, RAMP[3], "rivals at $20")]:
        pi = [profits([x, rival, rival], mp)[0] for x in p]
        ax.plot(p, pi, color=col, lw=1.5)
        k = int(np.argmax(pi))
        ax.scatter([p[k]], [pi[k]], s=14, color=col, zorder=5, edgecolors="white", linewidths=1)
        ax.text(p[k] + 0.35, pi[k] + 90, lab, ha="left", va="bottom", fontsize=6.4, color=INK2)
    for x, t in [(13.70, "Competitive\n$13.70"), (20.0, "Monopoly\n$20.00")]:
        ax.axvline(x, color=BASE, lw=0.7, zorder=1)
        ax.text(x + 0.25, 4300, t, fontsize=6.2, color=MUTED, va="top")
    ax.set_xlim(10, 26)
    ax.set_ylim(0, 4400)
    ax.set_xticks([10, 14, 18, 22, 26])
    ax.set_xticklabels([f"${t}" for t in [10, 14, 18, 22, 26]])
    ax.set_yticks([0, 1000, 2000, 3000, 4000])
    ax.set_yticklabels(["0", "$1k", "$2k", "$3k", "$4k"])
    ax.set_xlabel("Your price")
    ax.set_title("Your profit per round")
    save(fig, "dilemma")


# ---------------------------------------------------------------- 8. GRAFT arms
def graft_frame():
    from hawthorne.metrics import load_episodes
    rows = []
    v1 = {"naive__both": "Naive RFT", "filter__both": "Filter", "graft__retain_only": "GRAFT",
          "graftcot__retain_only": "GRAFT-CoT", "graftpp__retain_only": "GRAFT++"}
    blind = {"graftblind__retain_only": "GRAFT", "graftppblind_hard__retain_only": "GRAFT++",
             "graftppblind__retain_only": "GRAFT++ (soft)"}
    for d, lab in v1.items():
        p = ROOT / "results" / "eval" / d
        if p.exists():
            _, e = load_episodes(p)
            rows.append(e.assign(arm=lab, exp="v1"))
    for d, lab in blind.items():
        p = ROOT / "results" / "eval_blind" / d
        if p.exists() and len(list(p.glob("*.json"))) >= 24:
            _, e = load_episodes(p)
            rows.append(e.assign(arm=lab, exp="blind"))
    _, b = load_episodes(ROOT / "results" / "main")
    b = b[(b.goal == "profit") & (b.stakes.fillna("base").isin(["base", None])) & (~b.pressure.astype(bool))]
    rows.append(b.assign(arm="Base model", exp="v1"))
    E = pd.concat(rows, ignore_index=True)
    E["condition"] = E["condition"].astype(str)
    return E[E.condition.isin(THREE)]


def fig_graft():
    E = graft_frame()
    fig = plt.figure(figsize=(W, 2.35))
    gs = fig.add_gridspec(1, 2, width_ratios=[6, 3.2], wspace=0.12)
    for gi, (exp, arms, title) in enumerate([
        ("v1", ["Base model", "Naive RFT", "Filter", "GRAFT", "GRAFT-CoT", "GRAFT++"], "a   Original training set"),
        ("blind", ["GRAFT", "GRAFT++", "GRAFT++ (soft)"], "b   Text-blind training set")]):
        ax = fig.add_subplot(gs[gi], sharey=None if gi == 0 else fig.axes[0])
        sub = E[E.exp == exp] if exp == "blind" else E[(E.exp == "v1")]
        ax.set_ylim(-0.12, 1.1)
        ax.set_xlim(-0.7, len(arms) * 4 - 1.3)
        for g, a in enumerate(arms):
            s = sub[sub.arm == a]
            if not len(s):
                ax.text(g * 4 + 1, 0.05, "pending", ha="center", fontsize=6.4, color=MUTED)
            for i, c in enumerate(THREE):
                v = s[s.condition == c]["collusion_index"]
                if not len(v):
                    continue
                rbar(ax, g * 4 + i, v.mean(), 0.66, COND[c])
            nice = {"Base model": "Base\nmodel", "Naive RFT": "Naive\nRFT", "GRAFT-CoT": "GRAFT\n-CoT",
                    "GRAFT++ (soft)": "GRAFT++\n(soft)"}.get(a, a)
            ax.text(g * 4 + 1, -0.17, nice, ha="center", va="top", fontsize=6.6, transform=ax.transData,
                    linespacing=1.05)
        ax.axhline(0, color=BASE, lw=0.7)
        ax.set_xticks([])
        ax.set_yticks([0, 0.5, 1])
        if gi:
            ax.tick_params(labelleft=False)
        ax.set_title(title)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COND[c]) for c in THREE]
    fig.legend(handles, [LABEL[c] for c in THREE], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.17),
               handlelength=0.9, columnspacing=1.8)
    save(fig, "graft")
    s = E.groupby(["exp", "arm", "condition"])["collusion_index"].agg(["mean", "sem", "count"]).round(3)
    s.to_csv(OUT / "graft_summary.csv")
    print(s.to_string())


if __name__ == "__main__":
    fig_traj()
    fig_say_think_do()
    fig_explicit()
    fig_control()
    fig_goals()
    fig_pressure()
    fig_dilemma()
    fig_graft()
