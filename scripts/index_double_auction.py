"""Index every double-auction run in double_auction/results (one row per run folder).

    python scripts/index_double_auction.py

Reads each run's experiment_metadata.json and collusion_metrics.json and writes double_auction/runs_index.csv
plus a per-experiment summary, double_auction/experiments.csv. Run folders are named <date>_<time>_<tag>, where the tag
starts with the experiment code (E2p, NM, ...) and ends with the seed (_s0).
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DA = ROOT / "double_auction"
RES = DA / "results"

EXPERIMENTS = {
    "E0": "Smoke test and cost check",
    "E1": "Cartel ladder in Market A: instructed consortium, CEO pressure, no chat, silent cartel, monopoly, told to compete",
    "E2": "Main monitor experiment, first wave, and the saved 8-round cartels the continuations start from",
    "E2p": "Paired continuations of the saved cartels: monitor arms (none, silent, told, fined with 1/2/all read, random, told to dodge), reminder removed, resets, CEO pressure, hidden damages",
    "E4p": "Hidden-channel continuations: rivals' asks and trades hidden",
    "E9": "Sting seller and honest entrant in Market A",
    "E9p": "Paired controls for the sting and entrant runs",
    "E11": "GPT-4.1 formation gate (five sellers, CEO-pressure recipe, 30 rounds) and its Qwen3-14B twin",
    "E11p": "GPT-4.1 continuations under the monitor arms",
    "E11smoke": "GPT-4.1 smoke tests",
    "E12": "CEO price target of $95, enforced or words only",
    "E12smoke": "Price-target smoke test",
    "E13p": "Active entrant at the branch: scripted undercutter or a fresh AI competitor",
    "E13smoke": "Entrant smoke tests",
    "E14p": "Newcomer told to compete joins a formed cartel",
    "F1": "Formation pilot without any instruction (3 sellers, 2 buyers, 40 rounds)",
    "NM": "Market B (sellers with different costs, buyers that bargain): formation with GPT-4.1 and Qwen3-14B",
    "NMf": "Market B forks from formed worlds: deviation, hidden damages, undercutter",
    "PFP": "Price-fixing under pressure, first run (invalid: provider outage, see provenance/LOG.md)",
    "PFPv2": "Price-fixing under pressure v2, smoke run",
    "PFP2": "Price-fixing under pressure v2 (5 arms x 3 worlds)",
}

NAME = re.compile(r"^(\d{8})_(\d{6})_(.+?)(?:_s(\d+))?$")


def short(models) -> str:
    ms = sorted({m.split("/")[-1] for m in (models or []) if m})
    return "+".join(ms)


def main():
    rows = []
    for d in sorted(p for p in RES.iterdir() if p.is_dir() and NAME.match(p.name)):
        date, time, tag, seed = NAME.match(d.name).groups()
        exp = tag.split("_")[0]
        meta = json.loads((d / "experiment_metadata.json").read_text()) if (d / "experiment_metadata.json").exists() else {}
        met = json.loads((d / "collusion_metrics.json").read_text()) if (d / "collusion_metrics.json").exists() else {}
        cfg = meta.get("auction_config", {})
        parent = meta.get("resumed_from")
        rows.append({
            "run": d.name, "date": f"{date[:4]}-{date[4:6]}-{date[6:]}", "time": f"{time[:2]}:{time[2:4]}",
            "experiment": exp, "tag": tag, "seed": seed or cfg.get("seed", ""),
            "sellers": short(cfg.get("seller_models")), "buyers": short(cfg.get("buyer_models")),
            "n_sellers": len(cfg.get("seller_models") or []), "n_buyers": len(cfg.get("buyer_models") or []),
            "rounds": cfg.get("rounds", ""), "seller_chat": cfg.get("seller_comms_enabled", ""),
            "monitor": cfg.get("monitor_mode", "") if cfg.get("monitor_start_round") is not None else "",
            "monitor_read": cfg.get("monitor_n_watched", ""), "monitor_fine": cfg.get("monitor_fine", ""),
            "monitor_announced": cfg.get("monitor_announce", ""), "ceo_pressure": cfg.get("boss_pressure", ""),
            "prompt": cfg.get("seller_prompt_template", ""),
            "branched_from": re.split(r"[\\/]", parent)[-1] if parent else "", "branch_round": meta.get("branch_round", ""),
            "trades": met.get("num_trades", ""),
            "avg_trade_price": round(met["avg_trade_price_overall"], 2) if isinstance(met.get("avg_trade_price_overall"), (int, float)) else "",
            "has_messages": (d / "monitor_log.jsonl").exists() or (d / "unified.log").exists(),
            "files": sum(1 for _ in d.iterdir()),
        })
    with open(DA / "runs_index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    by = defaultdict(list)
    for r in rows:
        by[r["experiment"]].append(r)
    with open(DA / "experiments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["experiment", "runs", "models", "first", "last", "description"])
        for e in sorted(by, key=lambda k: (min(r["date"] + r["time"] for r in by[k]))):
            rs = by[e]
            models = sorted({r["sellers"] for r in rs if r["sellers"]})
            w.writerow([e, len(rs), "; ".join(models), min(r["date"] + " " + r["time"] for r in rs),
                        max(r["date"] + " " + r["time"] for r in rs), EXPERIMENTS.get(e, "")])
    unknown = sorted(set(by) - set(EXPERIMENTS))
    print(f"{len(rows)} runs in {len(by)} experiments -> {DA / 'runs_index.csv'}, {DA / 'experiments.csv'}")
    if unknown:
        print("  no description for:", unknown)


if __name__ == "__main__":
    main()
