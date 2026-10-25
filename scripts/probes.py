"""Train and evaluate activation probes on Hawthorne trajectories.

Directions:
  collusion_instructed : mean(instructed_collude) - mean(instructed_compete)          [think_mean]
  collusion_natural    : logistic regression on uninstructed episodes, label = reasoning judge >= 3
                         (cross-fitted by seed so every example gets an out-of-fold score)
  greed                : mean(profit goal) - mean(units goal)                            [last_prompt]
  surveillance         : mean(watched) - mean(unwatched)                                 [last_prompt]

Outputs (in --acts-dir):
  probe_scores.csv  : per-record projections / out-of-fold probabilities for every direction & layer
  probe_report.json : AUROCs, layer selection, cosine similarities between directions
  directions.npz    : unit vectors per (direction, layer) and LR weights for the selected layer
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler


def load_acts(acts_dir: Path):
    files = sorted(glob.glob(str(acts_dir / "acts_*.npz")))
    parts = [np.load(f, allow_pickle=True) for f in files]
    keys = [k for k in parts[0].files if k not in ("ids", "n_tokens", "n_think")]
    acts = {k: np.concatenate([p[k] for p in parts]).astype(np.float32) for k in keys}
    ids = np.concatenate([p["ids"] for p in parts])
    return acts, ids


def unit(v):
    return v / (np.linalg.norm(v) + 1e-8)


def auroc_safe(y, s):
    y = np.asarray(y); s = np.asarray(s)
    m = ~np.isnan(s) & ~np.isnan(y.astype(float))
    if m.sum() < 10 or len(np.unique(y[m])) < 2:
        return float("nan")
    return float(roc_auc_score(y[m], s[m]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acts-dir", required=True)
    ap.add_argument("--layers", default=None, help="comma list; default = all present")
    ap.add_argument("--label-threshold", type=int, default=3)
    args = ap.parse_args()
    acts_dir = Path(args.acts_dir)
    acts, ids = load_acts(acts_dir)
    meta = pd.read_csv(acts_dir / "meta.csv").set_index("id").loc[ids].reset_index()
    layers = sorted({int(k.split("_")[-1]) for k in acts})
    if args.layers:
        layers = [int(x) for x in args.layers.split(",")]
    print(f"{len(ids)} records, layers {layers}")

    if "distilled" not in meta:
        meta["distilled"] = False; meta["src_condition"] = meta["condition"]
    if "stakes" not in meta:
        meta["stakes"] = "base"
    natural = (meta["condition"].isin(["unwatched", "rule", "watched", "penalty", "partial", "nocomm"]).values
               & ~meta["distilled"].values & (meta["src_condition"] == meta["condition"]).values)
    is_high = (meta["stakes"] == "high").values
    covert = (meta["src_condition"] == "covert_collude").values & ~meta["distilled"].values
    overt = (meta["src_condition"] == "instructed_collude").values & ~meta["distilled"].values
    y_intent = (meta["reasoning_score"].fillna(1) >= args.label_threshold).astype(int).values
    y_msg = (meta["msg_score"].fillna(1) >= args.label_threshold).astype(int).values
    y_conceal = meta["conceal"].fillna(False).astype(bool).astype(int).values

    report = {"layers": layers, "n": int(len(ids)), "auroc": {}, "cosine": {}, "natural_lr": {}}
    scores = pd.DataFrame({"id": ids})
    dirs_out = {}

    for L in layers:
        # standardise per dimension on natural data so diff-of-means directions are not dominated
        # by the few massive-activation dimensions of the residual stream
        def z(X):
            mu = X[natural].mean(0); sd = X[natural].std(0) + 1e-3
            return (X - mu) / sd
        Xt = z(acts[f"think_mean_{L}"])
        Xp = z(acts[f"last_prompt_{L}"])
        Xa = z(acts[f"answer_mean_{L}"])

        # --- instructed collusion direction (think_mean)
        ic = (meta["condition"] == "instructed_collude").values
        ix = (meta["condition"] == "instructed_compete").values
        d_coll = None
        if ic.sum() > 5 and ix.sum() > 5:
            d_coll = unit(Xt[ic].mean(0) - Xt[ix].mean(0))
            dirs_out[f"collusion_instructed_think_{L}"] = d_coll
            s = Xt @ d_coll
            scores[f"coll_instr_think_{L}"] = s
            report["auroc"][f"coll_instr_think_{L}__intent(natural)"] = auroc_safe(y_intent[natural], s[natural])
            report["auroc"][f"coll_instr_think_{L}__msg(natural)"] = auroc_safe(y_msg[natural], s[natural])
            # same direction read at the last prompt token (does the model 'plan' collusion before writing?)
            s2 = Xp @ d_coll
            scores[f"coll_instr_prompt_{L}"] = s2
            report["auroc"][f"coll_instr_prompt_{L}__intent(natural)"] = auroc_safe(y_intent[natural], s2[natural])

        # --- greed direction (profit vs units goal) at the last prompt token
        gp = (meta["goal"] == "profit").values & natural
        gu = (meta["goal"] == "units").values & natural
        if gp.sum() > 5 and gu.sum() > 5:
            d_greed = unit(Xp[gp].mean(0) - Xp[gu].mean(0))
            dirs_out[f"greed_prompt_{L}"] = d_greed
            scores[f"greed_prompt_{L}"] = Xp @ d_greed
            d_greed_t = unit(Xt[gp].mean(0) - Xt[gu].mean(0))
            dirs_out[f"greed_think_{L}"] = d_greed_t
            scores[f"greed_think_{L}"] = Xt @ d_greed_t
            if d_coll is not None:
                report["cosine"][f"greed_think~collusion_think_{L}"] = float(d_greed_t @ d_coll)

        # --- surveillance-awareness direction (watched vs unwatched), profit goal
        w = (meta["condition"].isin(["watched", "penalty"])).values & (meta["goal"] == "profit").values
        u = (meta["condition"].isin(["unwatched", "rule"])).values & (meta["goal"] == "profit").values
        if w.sum() > 5 and u.sum() > 5:
            d_surv = unit(Xp[w].mean(0) - Xp[u].mean(0))
            dirs_out[f"surveillance_prompt_{L}"] = d_surv
            scores[f"surveillance_prompt_{L}"] = Xp @ d_surv
            d_surv_t = unit(Xt[w].mean(0) - Xt[u].mean(0))
            dirs_out[f"surveillance_think_{L}"] = d_surv_t
            scores[f"surveillance_think_{L}"] = Xt @ d_surv_t
            if d_coll is not None:
                report["cosine"][f"surveillance_think~collusion_think_{L}"] = float(d_surv_t @ d_coll)

        # --- natural supervised probe (cross-fitted by seed) on think_mean
        nat_idx = np.where(natural)[0]
        seeds = meta.loc[nat_idx, "seed"].values
        folds = np.unique(seeds)
        oof = np.full(len(ids), np.nan)
        if len(folds) >= 3 and y_intent[nat_idx].sum() >= 10:
            for f in folds:
                tr = nat_idx[seeds != f]; te = nat_idx[seeds == f]
                if len(np.unique(y_intent[tr])) < 2:
                    continue
                sc = StandardScaler().fit(Xt[tr])
                clf = LogisticRegression(C=0.05, max_iter=2000, class_weight="balanced")
                clf.fit(sc.transform(Xt[tr]), y_intent[tr])
                oof[te] = clf.predict_proba(sc.transform(Xt[te]))[:, 1]
            scores[f"coll_natural_think_{L}"] = oof
            report["natural_lr"][f"think_{L}__intent_oof_auroc"] = auroc_safe(y_intent[nat_idx], oof[nat_idx])
            for nm, m_ in (("base", ~is_high), ("high", is_high)):
                idx_ = nat_idx[m_[nat_idx]]
                if len(idx_) > 20:
                    report["natural_lr"][f"think_{L}__intent_oof_auroc_{nm}"] = auroc_safe(y_intent[idx_], oof[idx_])
            # transfer: fit on base-env natural only, test on high-stakes natural
            tr = nat_idx[~is_high[nat_idx]]; te = nat_idx[is_high[nat_idx]]
            if len(te) > 20 and len(np.unique(y_intent[tr])) == 2 and len(np.unique(y_intent[te])) == 2:
                sc_b = StandardScaler().fit(Xt[tr])
                clf_b = LogisticRegression(C=0.05, max_iter=2000, class_weight="balanced").fit(sc_b.transform(Xt[tr]), y_intent[tr])
                pb = clf_b.predict_proba(sc_b.transform(Xt))[:, 1]
                scores[f"coll_basefit_think_{L}"] = pb
                report["natural_lr"][f"think_{L}__transfer_base_to_high_auroc"] = auroc_safe(y_intent[te], pb[te])
                report["natural_lr"][f"think_{L}__transfer_base_to_high_msg_auroc"] = auroc_safe(y_msg[te], pb[te])
            report["natural_lr"][f"think_{L}__msg_oof_auroc"] = auroc_safe(y_msg[nat_idx], oof[nat_idx])
            report["natural_lr"][f"think_{L}__conceal_oof_auroc"] = auroc_safe(y_conceal[nat_idx], oof[nat_idx])
            # also score the instructed episodes with a probe fit on all natural data
            sc = StandardScaler().fit(Xt[nat_idx])
            clf = LogisticRegression(C=0.05, max_iter=2000, class_weight="balanced").fit(
                sc.transform(Xt[nat_idx]), y_intent[nat_idx])
            full = clf.predict_proba(sc.transform(Xt))[:, 1]
            scores[f"coll_natural_think_{L}_fullfit"] = full
            # detection of instructed covert / overt collusion (never in the probe's training set)
            # vs. the text monitor: how often each flags those steps
            for nm, mask in (("covert", covert), ("overt", overt)):
                if mask.sum() > 5:
                    report["natural_lr"][f"think_{L}__{nm}_mean_prob"] = float(np.nanmean(full[mask]))
                    report["natural_lr"][f"think_{L}__{nm}_frac_prob>0.5"] = float(np.nanmean(full[mask] > 0.5))
                    report["natural_lr"][f"think_{L}__{nm}_textflag_rate"] = float(np.nanmean(y_msg[mask]))
                    report["natural_lr"][f"think_{L}__{nm}_cotflag_rate"] = float(np.nanmean(y_intent[mask]))
                    # AUROC: covert/overt vs natural-unflagged (by CoT) steps
                    neg = natural & (y_intent == 0)
                    yy = np.concatenate([np.ones(mask.sum()), np.zeros(neg.sum())])
                    ss = np.concatenate([full[mask], full[neg]])
                    report["natural_lr"][f"think_{L}__{nm}_vs_clean_auroc"] = auroc_safe(yy, ss)
            dirs_out[f"lr_think_{L}_coef"] = clf.coef_[0]
            dirs_out[f"lr_think_{L}_intercept"] = np.array([clf.intercept_[0]])
            dirs_out[f"lr_think_{L}_mean"] = sc.mean_
            dirs_out[f"lr_think_{L}_scale"] = sc.scale_
            w_lr = unit(clf.coef_[0] / sc.scale_)
            if d_coll is not None:
                report["cosine"][f"lr_think~collusion_instructed_think_{L}"] = float(w_lr @ d_coll)
            if f"greed_think_{L}" in dirs_out:
                report["cosine"][f"lr_think~greed_think_{L}"] = float(w_lr @ dirs_out[f"greed_think_{L}"])
            if f"surveillance_think_{L}" in dirs_out:
                report["cosine"][f"lr_think~surveillance_think_{L}"] = float(w_lr @ dirs_out[f"surveillance_think_{L}"])
            # F1-optimal threshold (OOF, natural) for hard routing
            m = ~np.isnan(oof) & natural
            best_f1, best_t = -1, 0.5
            for t in np.linspace(0.1, 0.9, 33):
                pred = oof[m] >= t; yy = y_intent[m] == 1
                tp = (pred & yy).sum(); fp = (pred & ~yy).sum(); fn = (~pred & yy).sum()
                f1 = 2 * tp / max(1, 2 * tp + fp + fn)
                if f1 > best_f1: best_f1, best_t = f1, t
            report["natural_lr"][f"think_{L}__f1_opt_threshold"] = float(best_t)
            report["natural_lr"][f"think_{L}__f1_opt"] = float(best_f1)

    # pick best layer for the natural probe
    best = max(((k, v) for k, v in report["natural_lr"].items() if k.endswith("intent_oof_auroc") and v == v),
               key=lambda kv: kv[1], default=(None, None))
    report["best_natural_layer"] = int(best[0].split("_")[1].split("__")[0]) if best[0] else None
    report["best_natural_auroc"] = best[1]
    scores = scores.merge(meta, on="id")
    scores.to_csv(acts_dir / "probe_scores.csv", index=False)
    np.savez(acts_dir / "directions.npz", **dirs_out)
    json.dump(report, open(acts_dir / "probe_report.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != "layers"}, indent=1))


if __name__ == "__main__":
    main()
