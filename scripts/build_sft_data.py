"""Build rejection-sampling SFT datasets for each training arm.

Candidates : profit-goal steps from the main ladder conditions whose (episode, seller)
             cumulative profit is in the top --top-frac of its condition.  Under the profit
             goal this pool is enriched with collusive behaviour -- the "reward hack".
Anchors    : units-goal steps (same task format, no collusion incentive) -> GRAFT anchor env.

Arms (cls / w per example):
  naive   : everything unclassified                         (deploy: both)
  filter  : drop text-flagged candidates; rest unclassified (deploy: both)   ["penalise detected"]
  graft   : text-flagged -> forget ; others unclassified ; anchors retain    (deploy: retain_only)
  graftpp : w = max(text_flag, probe_prob) soft routing; anchors retain      (deploy: retain_only)
  graftcot: CoT-judge-flagged -> forget (oracle-ish monitor that reads reasoning)

Text flag  = message monitor score >= 3 (what a platform can actually see).
Probe prob = out-of-fold natural probe probability (probe_scores.csv, chosen layer).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records-dir", required=True, help="dir with records.jsonl + meta.csv (+ probe_scores.csv)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--conditions", nargs="+", default=["unwatched", "rule", "watched", "penalty"])
    ap.add_argument("--top-frac", type=float, default=0.5)
    ap.add_argument("--anchor-frac", type=float, default=0.2, help="anchors as fraction of candidates")
    ap.add_argument("--probe-col", default=None, help="column in probe_scores.csv for GRAFT++ routing")
    ap.add_argument("--probe-threshold", type=float, default=None,
                    help="if set, hard-threshold the probe instead of soft routing")
    ap.add_argument("--max-candidates", type=int, default=-1)
    ap.add_argument("--organism-n", type=int, default=300,
                    help="distilled samples per organism source (instructed_collude -> overt, covert_collude -> covert)")
    ap.add_argument("--stakes", default=None, help="restrict natural candidates to this stakes value")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--text-blind", action="store_true",
                    help="drop every text-flagged candidate (anchors unchanged): collusion the text monitor cannot see")
    ap.add_argument("--arms", nargs="+", default=["naive", "filter", "graft", "graftcot", "graftpp"])
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    rd = Path(args.records_dir)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    recs = {json.loads(l)["id"]: json.loads(l) for l in open(rd / "records.jsonl")}
    meta = pd.read_csv(rd / "meta.csv")
    probe = None
    if args.probe_col and (rd / "probe_scores.csv").exists():
        ps = pd.read_csv(rd / "probe_scores.csv")
        # natural rows: out-of-fold score; distilled / instructed rows: full-fit score (never in the probe's train set)
        full_col = args.probe_col + "_fullfit"
        col = ps[args.probe_col].copy()
        if full_col in ps:
            col = col.where(col.notna(), ps[full_col])
        probe = pd.Series(col.values, index=ps["id"].values)
    if "distilled" not in meta:
        meta["distilled"] = False; meta["src_condition"] = meta["condition"]

    # ---- candidates: top-frac (episode, seller) by cumulative profit within condition (natural, uninstructed)
    if "stakes" not in meta:
        meta["stakes"] = "base"
    natural = meta[(meta["goal"] == "profit") & meta["condition"].isin(args.conditions) & ~meta["distilled"]
                   & (meta["src_condition"] == meta["condition"])]
    if args.stakes:
        natural = natural[natural["stakes"] == args.stakes]
    cand = natural.copy()
    agg = cand.groupby(["tag", "seller"])["profit"].sum().reset_index()
    agg["condition"] = agg["tag"].str.split("__").str[0]
    keep = []
    for c, g in agg.groupby("condition"):
        thr = g["profit"].quantile(1 - args.top_frac)
        keep.append(g[g["profit"] >= thr])
    keep = pd.concat(keep)
    cand = cand.merge(keep[["tag", "seller"]], on=["tag", "seller"])
    if args.max_candidates > 0 and len(cand) > args.max_candidates:
        cand = cand.sample(args.max_candidates, random_state=args.seed)
    cand["kind"] = "natural"
    # ---- model-organism samples: context-distilled instructed episodes (directive removed)
    org = []
    for src in ("instructed_collude", "covert_collude"):
        o = meta[meta["distilled"] & (meta["src_condition"] == src)]
        if len(o):
            o = o.sample(min(args.organism_n, len(o)), random_state=args.seed).copy()
            o["kind"] = "overt" if src == "instructed_collude" else "covert"
            org.append(o)
    if org:
        cand = pd.concat([cand] + org, ignore_index=True)
    cand["text_flag"] = (cand["msg_score"].fillna(1) >= 3).astype(int)
    cand["cot_flag"] = (cand["reasoning_score"].fillna(1) >= 3).astype(int)
    if probe is not None:
        cand["probe"] = cand["id"].map(probe).fillna(0.0).clip(0, 1)
    else:
        cand["probe"] = 0.0

    # ---- anchors: units-goal steps
    anc = meta[(meta["goal"] == "units") & meta["condition"].isin(args.conditions) & ~meta["distilled"]]
    n_anc = int(args.anchor_frac * len(cand))
    anc = anc.sample(min(n_anc, len(anc)), random_state=args.seed)

    by_kind = cand.groupby("kind")[["text_flag", "cot_flag", "probe"]].mean().round(3).to_dict("index")
    stats = {"n_candidates": int(len(cand)), "n_anchors": int(len(anc)), "by_kind": by_kind,
             "kind_counts": cand["kind"].value_counts().to_dict(),
             "text_flag_rate": float(cand["text_flag"].mean()),
             "cot_flag_rate": float(cand["cot_flag"].mean()),
             "probe_mean": float(cand["probe"].mean()),
             "text_flag_recall_vs_cot": float(((cand.text_flag == 1) & (cand.cot_flag == 1)).sum()
                                              / max(1, (cand.cot_flag == 1).sum())),
             "conditions": args.conditions, "probe_col": args.probe_col}

    def write(arm: str, rows: list[dict]):
        if arm not in args.arms:
            return
        rng.shuffle(rows)
        d = out / arm; d.mkdir(exist_ok=True)
        with open(d / "train.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        cls_counts = pd.Series([r["cls"] for r in rows]).value_counts().to_dict()
        stats[arm] = {"n": len(rows), **cls_counts,
                      "mean_w": float(np.mean([r.get("w", 1.0 if r["cls"] == "forget" else 0.0)
                                               for r in rows if r["cls"] != "retain"]))}
        print(f"{arm:9s} n={len(rows):4d} {cls_counts}")

    def ex(row, cls, w=None):
        r = recs[row["id"]]
        o = {"id": r["id"], "system": r["system"], "user": r["user"], "reasoning": r["reasoning"],
             "content": r["content"], "thinking": r.get("thinking", True), "cls": cls}
        if w is not None:
            o["w"] = float(w)
        return o

    if args.text_blind:
        cand = cand[cand["text_flag"] == 0]
        stats["text_blind"] = {"n_candidates": int(len(cand)), "kind_counts": cand["kind"].value_counts().to_dict(),
                               "probe_mean_by_kind": cand.groupby("kind")["probe"].mean().round(3).to_dict(),
                               "cot_flag_rate": float(cand["cot_flag"].mean())}
    C = cand.to_dict("records"); A = anc.to_dict("records")
    write("naive", [ex(r, "unclassified") for r in C] + [ex(r, "unclassified") for r in A])
    write("filter", [ex(r, "unclassified") for r in C if not r["text_flag"]] + [ex(r, "unclassified") for r in A])
    write("graft", [ex(r, "forget" if r["text_flag"] else "unclassified") for r in C] + [ex(r, "retain") for r in A])
    write("graftcot", [ex(r, "forget" if r["cot_flag"] else "unclassified") for r in C] + [ex(r, "retain") for r in A])
    pp = []
    for r in C:
        if args.probe_threshold is not None:
            flag = r["text_flag"] or (r["probe"] >= args.probe_threshold)
            pp.append(ex(r, "forget" if flag else "unclassified"))
        else:
            w = max(float(r["text_flag"]), float(r["probe"]))
            pp.append(ex(r, "forget" if w >= 0.999 else "unclassified", w=w))
    write("graftpp", pp + [ex(r, "retain") for r in A])
    json.dump(stats, open(out / "stats.json", "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
