# **GRAFT++: reducing collusive behaviour in agents via localized training and white-box (activation-probe) gradient routing.**

Apart Research — AI Collusion Research Sprint (Oct 23–25, 2026). Track 3, RQ 3.4 (+ 2.3).

> The *Hawthorne effect*: people change their behaviour when they know they are being observed.
> We ask the same question of LLM coalitions.

## What is in here

| Component | Path | What it does |
|---|---|---|
| **Hawthorne Market** environment | `hawthorne/market.py`, `hawthorne/prompts.py`, `hawthorne/episode.py` | 3 Qwen3-14B seller agents, 20 rounds, calibrated logit demand (Calvano et al. 2020 ×10, Nash $13.70 / monopoly $20.00), a seller text channel, an LLM compliance monitor and an optional balance penalty. Two objectives: **gross profit** (collusion incentive) vs **units sold** (no collusion incentive — the "nothing to hide" control). |
| Condition ladder | `hawthorne/prompts.py` | `unwatched → rule → watched → penalty (→ partial)`; each step adds exactly one factor. Controls: `nocomm`, `instructed_collude`, `instructed_compete`. |
| Monitors | `hawthorne/prompts.py` | Text monitor (what a platform can see) and a research-only CoT monitor over the agent's native `<think>` reasoning (intent + concealment). |
| Metrics / analysis | `hawthorne/metrics.py`, `scripts/analyze.py` | Collusion index, dispersion, say–think gap, price-change correlation (tacit coordination), event study around the first fine. |
| Activation probes | `modal_app/activations.py`, `scripts/probes.py` | Residual-stream features at the last prompt token, mean over `<think>`, mean over answer. Collusion (instructed and natural LR), greed, surveillance-awareness directions. |
| GRAFT / GRAFT++ | `modal_app/graft_train.py`, `scripts/build_sft_data.py` | Dual-LoRA gradient-routed SFT on rejection-sampled trajectories. GRAFT routes on the text monitor; **GRAFT++ routes on the model's own activations** (soft weights from a collusion-intent probe). Merge RETAIN → deploy with vLLM. |
| Eval | `scripts/eval_arms.py` | Evaluate every trained checkpoint in the same environment with a fixed (base-model) judge. |
| Serving | `modal_app/serve_vllm.py` | Qwen3-14B with `--reasoning-parser qwen3` on Modal H100s. |

All code in this repository was written during the sprint. GRAFT is re-implemented from the description in
Ward*, Hu* et al. (2026) and their public code (MIT); nothing is vendored.

## Reproduce

```bash
pip install -r requirements.txt && pip install modal && modal setup
modal deploy modal_app/serve_vllm.py                       # Qwen3-14B server (thinking on)
export HAWTHORNE_BASE_URL=https://<workspace>--hawthorne-vllm-base-server.us-east.modal.direct/v1

# 1. ladder experiment
python scripts/run_grid.py --base-url $HAWTHORNE_BASE_URL \
    --conditions unwatched rule watched penalty --goals profit units --seeds 0-9 --out results/main
python scripts/run_grid.py --base-url $HAWTHORNE_BASE_URL \
    --conditions nocomm instructed_collude instructed_compete --goals profit --seeds 0-4 --out results/main
python scripts/analyze.py --results results/main --out figures/main

# 2. activations + probes
python scripts/build_records.py --dirs results/main --out data/main
modal volume put hawthorne-data data/main /main
modal run modal_app/activations.py --name main --shards 6
modal volume get hawthorne-data /main data/main --force
python scripts/probes.py --acts-dir data/main

# 3. GRAFT / GRAFT++
python scripts/build_sft_data.py --records-dir data/main --out data/sft --probe-col coll_natural_think_<L>
for arm in naive filter graft graftpp; do modal volume put hawthorne-data data/sft/$arm /$arm; done
modal run modal_app/graft_train.py --run graft --merge-configs retain_only,both,forget_only   # etc.

# 4. evaluate arms (judge = base model)
python scripts/eval_arms.py --base-url $HAWTHORNE_BASE_URL --models naive__both filter__both graft__retain_only graftpp__retain_only
```

## Report

`report/` contains the sprint report (PDF) and figures.
