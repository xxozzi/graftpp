"""Flatten episode logs into records.jsonl (for activation extraction / SFT) + meta.csv."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hawthorne.prompts import EpisodeConfig, seller_system_prompt  # noqa: E402
from hawthorne.market import MarketParams, equilibria  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dirs", nargs="+", required=True)
    p.add_argument("--out", required=True, help="output directory (records.jsonl, meta.csv)")
    p.add_argument("--stakes", default=None, help="only episodes with this stakes value (e.g. high)")
    p.add_argument("--steer", default=None, help="only episodes with this steering label ('unsteered' = none)")
    p.add_argument("--distill", nargs="*", default=[],
                   help="src_condition:target_condition pairs; emits extra records whose system prompt is the "
                        "target condition's (directive removed), id suffix ::d")
    args = p.parse_args()
    distill = dict(x.split(":") for x in args.distill)
    mp = MarketParams(); eq = equilibria(mp)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    rows, n = [], 0
    with open(out / "records.jsonl", "w") as f:
        for d in args.dirs:
            for fp in sorted(Path(d).glob("*.json")):
                rec = json.load(open(fp))
                cfg = rec["config"]
                if args.stakes and cfg.get("stakes", "base") != args.stakes:
                    continue
                if args.steer and (cfg.get("steer", "") or "unsteered") != args.steer:
                    continue
                variants = [(cfg["condition"], rec["system_prompts"], False)]
                if cfg["condition"] in distill:
                    tcfg = EpisodeConfig(condition=distill[cfg["condition"]], goal=cfg["goal"], seed=cfg["seed"],
                                         n_rounds=cfg["n_rounds"], pressure=cfg.get("pressure", False),
                                         stakes=cfg.get("stakes", "base"))
                    variants.append((distill[cfg["condition"]], [seller_system_prompt(i, tcfg, mp, eq) for i in range(3)], True))
                for cond_out, sys_prompts, is_d in variants:
                  for s in rec["steps"]:
                    rid = f"{fp.stem}::r{s['round']}::s{s['seller']}" + ("::d" if is_d else "")
                    f.write(json.dumps({"id": rid, "system": sys_prompts[s["seller"]],
                                        "user": s["user_prompt"], "reasoning": s["reasoning"],
                                        "content": s["raw_response"],
                                        "thinking": cfg.get("thinking", True)}) + "\n")
                    rows.append({"id": rid, "tag": fp.stem, "condition": cond_out, "src_condition": cfg["condition"],
                                 "distilled": is_d,
                                 "goal": cfg["goal"], "pressure": bool(cfg.get("pressure", False)),
                                 "stakes": cfg.get("stakes", "base"),
                                 "steer": cfg.get("steer", "") or "unsteered",
                                 "seed": cfg["seed"], "round": s["round"],
                                 "seller": s["seller"], "price": s["price"], "units": s["units"],
                                 "profit": s["profit"], "message": s["message"],
                                 "msg_len": len(s["message"] or ""),
                                 "msg_score": s["msg_score"], "reasoning_score": s["reasoning_score"],
                                 "conceal": s["conceal"], "flagged": s["flagged"],
                                 "penalty": s["penalty"], "balance_after": s["balance_after"],
                                 "reasoning_chars": len(s["reasoning"] or ""),
                                 "p_nash": rec["equilibria"]["p_nash"],
                                 "p_mono": rec["equilibria"]["p_mono"]})
                    n += 1
    pd.DataFrame(rows).to_csv(out / "meta.csv", index=False)
    print(f"wrote {n} records -> {out}")


if __name__ == "__main__":
    main()
