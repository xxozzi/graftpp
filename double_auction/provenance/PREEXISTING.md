# Pre-existing work (required by the sprint rules)

Everything below existed before the sprint or was written by someone else. The report names each item.

| What | Source | How we use it |
|---|---|---|
| The starter repo: 10 harnesses, the Dolos challenge, the literature list and `poseidon_compute` | [poseidon-research/collusion_hackathon](https://github.com/poseidon-research/collusion_hackathon) at `d585a7b`, cloned into `vendor/` by `scripts/bootstrap.sh` (not committed) | inference routing (`poseidon_compute`) and reference material |
| The double-auction harness, hackathon edition (Agrawal et al. 2025, [arXiv 2507.01413](https://arxiv.org/abs/2507.01413)) | `llm-agent-collusion/` in the starter repo at `d585a7b`, copied to `src/double_auction` unmodified in commit `0b23a2c` (its 44 MB `data/` folder is not copied) | the market, sellers, ZIP buyers, overseer, judge and metrics |
| Our integration edits to it | commit `6118df8`: the path to `poseidon_compute`, and runs default to the repo-root `results/` | so it runs from this repo |
| Our fixes to upstream bugs (found by a pre-push code review, Oct 24) | each marked `CAIAC fix` in the code; tests in `src/double_auction/tests/test_caiac_fixes.py` | the Gini metric divided wrongly; evaluation crashed on a round with no bids, and when the competitive and cartel prices coincide; with both keys set, GPT overseer and judge calls went to Nebius; country demonyms never reached the prompt; the seller-mix scripts lacked `--sellers 5 --buyers 5`; keys kept only in `compute.env` missed the routing check for a run's first client; plotting a condition with no runs crashed; a Windows console (cp1252) crashed on the summary's symbols; analysis indexed comparison conditions that didn't exist |
| Known upstream issue we did not fix | `ZIPBuyer` in `market/agents.py`: its margin update is commented out, so it always bids about $80 | we use LLM buyers instead (PRD §3, §15) |
| Our experiment changes to it | listed here as they land (PRD §9) | the branching, watch policies, fines, notices, ask-blind mode and logs |
| Agrawal et al. (2025) shipped runs, `vendor/collusion_hackathon/llm-agent-collusion/data/` (75 runs; the 50 GPT-4.1 runs in five conditions) | not ours: the paper's own data at the starter repo's pinned commit; re-analysed by `src/analyze_agrawal_runs.py` -> `results/agrawal_reanalysis/` | the zero-cost GPT-4.1 panel in the report (chat / oversight / pressure / both); every number is labelled as a re-analysis of their runs |
| ColludeBench (`vendor/collusion_hackathon/steganographic-collusion/auditor/detectors/mi.py`, `auditor/pvalues.py`) | the plug-in mutual-information statistic and the +1-smoothed empirical p-value in `src/channel_measures.py` (used by `src/analyze.py` and `src/analyze_agrawal_runs.py`) are modelled on them (re-implemented, not copied) | the action-dependence statistic with a cross-run swap null and a round-permutation null |
| lit-sprint (`lit.py`) | Alfredo's literature tool, written before the sprint | literature searches and citation checks only, not the experiments |

Only if E6 runs: the J-space lenses at https://huggingface.co/neuronpedia/jacobian-lens and the code at
https://github.com/anthropics/jacobian-lens.

**License:** the starter repo has no license file. Ask the organizers before making a copy of the harness public.

Add a row for every file or function copied or adapted from somewhere else.

## Added Sun Oct 25 PM (new-market pilot)
- **Hidden damages (`--damages_rate`, `market.apply_damages`)**: our implementation of the expected-damages regulator of Garra (2026, arXiv 2609.13037, Section 5), itself after Harrington (2005): the deduction is the market's overpricing index times the seller's accumulated overcharge; the agents are not told the rule and see only the deduction. Adapted from a Bertrand pricing game to the double auction (per-trade overcharge above a reference price, the harness's own benchmarks for the index). The code is ours.
- **Responsive undercutter (`--entrant responsive`)**: a rule-based entrant that undercuts last hour's lowest incumbent ask, after the "active entrant" of Garra (2026) and the learning entrant of Bichler et al. (2026, arXiv 2610.21711); theirs are random or regret-matching, ours is a fixed response rule. The code is ours.
- **One-shot instructed deviation (`--force_ask`)**: the forced-deviation test of Calvano et al. (2020) adapted to an LLM seller (an instruction for one hour, message withheld). The code is ours.
- **Market B design** (3 sellers at $80 / $84 / $88, 4 buyers at $100 / $96 / $92 / $86): our own, chosen so that the harness's `competitive_equilibrium()` and `jpm_price()` give a 3-trade competitive outcome and a 2-trade cartel outcome; the reading of the paper's market as having no unique competitive price follows Struski et al. (2026, arXiv 2609.02580) and the standard equilibrium range for a double auction.
