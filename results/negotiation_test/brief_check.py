"""Print what the sellers' system prompt says about the market brief, for the arm set by the environment.

    python results/hawthorne_negotiation/brief_check.py --repo <clone>   (env: HAWTHORNE_NO_BRIEF / HAWTHORNE_BRIEF_GRID)

Builds both sellers' system prompts for the arm configuration (--variant maxprofit, unwatched, profit, 30 rounds,
negotiation on), prints their sha256 (so the patched copy with no variable set can be checked against his
unmodified code) and the text between "MARKET FACTS" and "SELLER CHANNEL".
"""
import argparse
import hashlib
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True)
ap.add_argument("--negotiate", type=int, default=1)
args = ap.parse_args()
sys.path.insert(0, args.repo)
from hawthorne.market import MarketParams, equilibria  # noqa: E402
from hawthorne.prompts import EpisodeConfig, seller_system_prompt  # noqa: E402

cfg = EpisodeConfig(condition="unwatched", goal="profit", seed=0, n_rounds=30, stakes="base", n_sellers=2,
                    memory=True, indefinite=True, negotiate=bool(args.negotiate))
mp = MarketParams(n_sellers=2)
eq = equilibria(mp)
sp = [seller_system_prompt(i, cfg, mp, eq) for i in range(2)]
print(f"repo={args.repo} HAWTHORNE_NO_BRIEF={os.environ.get('HAWTHORNE_NO_BRIEF')!r} "
      f"HAWTHORNE_BRIEF_GRID={os.environ.get('HAWTHORNE_BRIEF_GRID')!r} negotiate={cfg.negotiate}")
print("sha256 seller prompts:", [hashlib.sha256(s.encode()).hexdigest()[:16] for s in sp])
a = sp[0].index("MARKET FACTS")
b = sp[0].index("SELLER CHANNEL")
print(sp[0][a:b].rstrip())
print("-" * 60)
