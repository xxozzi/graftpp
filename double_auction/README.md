# Double-auction experiments

Our team's second set of experiments, run in a double auction instead of the Hawthorne pricing market. Sellers post asks,
buyers post bids, and trades clear each hour. It uses the organisers' auction harness from Agrawal et al. (2025),
with our fixes. Imported from [AlfredoFFD/apart-collusion-sprint](https://github.com/AlfredoFFD/apart-collusion-sprint)
at commit `54f4ec7` (25 Oct 2026). Every path quoted in `provenance/claims.md` and in the summary tables resolves
inside this folder. The paper's Section 4.4 ("A second
market and a second model") and its J-space paragraph are built from these files by `scripts/paper_market2.py`.

## Layout

| Path | What |
|---|---|
| `runs_index.csv` | one row per run: experiment, models, sellers and buyers, monitor settings, the run it branched from, trades, average trade price |
| `experiments.csv` | one row per experiment code: number of runs, models, first and last run, description |
| `results/<date>_<time>_<tag>/` | one folder per run (286 runs); the tag starts with the experiment code and ends with the seed (`_s0`) |
| `results/*.md`, `results/*.csv` | the summary tables (below) |
| `results/agrawal_reanalysis/` | Agrawal et al.'s 50 released GPT-4.1 runs re-scored with our judge prompt |
| `results/figures/` | the figures made from these tables |
| `results/_launch_logs/`, `results/_aborted/`, `results/_awareness_control/` | launch output, runs stopped early, the test-awareness control |
| `provenance/LOG.md` | the research log: every run with its time, command, result folder and reason, plus pre-registrations |
| `provenance/claims.md` | every reported number with the file and row it comes from |
| `provenance/PREEXISTING.md` | what came from the organisers' harness and what our team changed |
| `provenance/references.json` | 122 verified references |

## The two markets

- **Market A:** three sellers with cost $80 and three buyers with value $100. Any price from $80 to $100 clears every
  unit; the benchmark is $90 and the cartel price is $100. Price index: 0 at $90, 1 at $100.
- **Market B:** sellers with costs $80, $84 and $88; buyers with values $100, $96, $92 and $86. Competition clears 3
  trades at $88–92; a cartel at $96 sells 2 and must withhold one member's unit. Price index: 0 at $90, 1 at $96.

## Inside a run folder

| File | What |
|---|---|
| `experiment_metadata.json` | the full configuration (models, rounds, monitor mode, fines, prompts, seed) and the run it branched from |
| `unified.log` | the whole auction, hour by hour: asks, bids, trades, messages |
| `Seller <name>.md`, `Buyer <name>.md`, `Overseer.md` | each agent's prompts, private reasoning and replies |
| `monitor_log.jsonl` | the live monitor's reads, scores and fines |
| `collusion_metrics.json` | prices, trades, profits, collusion indices by hour |
| `fullview_scores.json`, `llm_eval_full.json` | the frozen judge's scores of every message and of the reasoning |
| `e7_jspace.json` | J-lens readout of the sellers' reasoning workspace |
| `auction_results.md` | a readable summary |

## Summary tables

| File | What |
|---|---|
| `E5_conditions.md`, `E5_runs.csv` | every condition's means with intervals, and per-run values (price index, trade price, coordinating messages, judge scores, flags, fines) |
| `DETECTOR.md`, `DETECTOR_runs.csv` | which signal finds a formed cartel: price versus the message monitor |
| `NEWMARKET.md` | Market B formation and forks |
| `ENTRANT.md`, `PHASE2.md` | entrants, newcomers, sting seller, resets |
| `PRESSURE_V2.md` | price-fixing under pressure |
| `F1_formation.md` | formation without an instruction |
| `thinking_scan.md`, `thinking_scan.csv`, `thinking_judge*.md` | keyword scan and frozen-judge reads of the private reasoning |
| `jspace_thinking_join.md` | J-lens readout joined with the reasoning and the message scores |
| `E3_replay*.csv` | replays of the monitor schedule over unmonitored runs |
| `enforcement_gate.md` | the Market B enforcement test |

## Experiments

| Code | Runs | What |
|---|---|---|
| E0 | 7 | Smoke test and cost check |
| E1 | 24 | Cartel ladder in Market A: instructed consortium, CEO pressure, no chat, silent cartel, monopoly, told to compete |
| E2 | 18 | Main monitor experiment, first wave, and the saved 8-round cartels the continuations start from |
| E2p | 72 | Paired continuations of the saved cartels: monitor arms (none, silent, told, fined with 1/2/all read, random, told to dodge), reminder removed, resets, CEO pressure, hidden damages |
| E4p | 18 | Hidden-channel continuations: rivals' asks and trades hidden |
| E9, E9p | 21 | Sting seller and honest entrant, with paired controls |
| E11, E11smoke | 8 | GPT-4.1 formation gate (five sellers, CEO-pressure recipe, 30 rounds) and its Qwen3-14B twin |
| E11p | 18 | GPT-4.1 continuations under the monitor arms |
| E12, E12smoke | 7 | CEO price target of $95, enforced or words only |
| E13p, E13smoke | 14 | Active entrant at the branch: scripted undercutter or a fresh AI competitor |
| E14p | 6 | Newcomer told to compete joins a formed cartel |
| F1 | 12 | Formation pilot without any instruction (3 sellers, 2 buyers, 40 rounds) |
| NM | 25 | Market B formation with GPT-4.1 and Qwen3-14B |
| NMf | 12 | Market B forks from formed worlds: deviation, hidden damages, undercutter |
| PFP, PFPv2, PFP2 | 24 | Price-fixing under pressure, with two follow-ups: the sentence that coordination is illegal removed, and the per-sale wording closed (the first run is invalid after a provider outage; see `provenance/LOG.md`) |

Rebuild the indexes with `python scripts/index_double_auction.py`.
