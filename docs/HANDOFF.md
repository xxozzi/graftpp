# HANDOFF — read this first (rewritten 2026-10-25 ~08:30 EDT)

HAWTHORNE project (Apart AI Collusion Research Sprint, RQ 3.4 + 2.3). Deadline: **Mon 2026-10-26 07:59 EDT**.
Chronology, every design decision, bugs and pre-specified rules: `docs/EXPERIMENT_LOG.md` (read its last third).

## Compute
- Active Modal workspace: `jayden-w-jeong`, CLI profile `hawthorne2` ($280 credit, ≈$148 spent at 08:15).
  Always pass `MODAL_PROFILE=hawthorne2`. Old workspace `jgj2122` (profile `jgj2122`) holds the original runs.
- Workspace GPU cap is 10 concurrent containers. All vLLM apps are deployed with min_containers=0 (scale to zero).
- Deployed apps: hawthorne-vllm-{base,judge,steer-desperation,steer-realness,steer-genuineness,
  naive--both,filter--both,graft--retain-only,graftcot--retain-only,graftpp--retain-only}.
  URL pattern: https://jayden-w-jeong--hawthorne-vllm-<name>-server.us-east.modal.direct/v1

## Done (all analysed; report drafted)
1. Base env ladder + controls (results/main, figures/main, figures/probes) — unchanged from before.
2. High-stakes 3-seller grid, 52/52 (results/main/*profitH*; figures/high; `scripts/compare_stakes.py`).
3. Collusive testbed (`run_grid.py --variant collusive`): pilot (results/collusive), lever pilots
   (results/collusive_{negotiate,negbar,neg750,hiddenbar,req750,naive}; results/_invalid/ = buggy, excluded),
   100-round ladder for unsteered + 3 steered arms (results/collusive_main, 80 eps) and the naive-RFT model
   (results/collusive_main_naive, 20 eps, exploratory). Analysis: `scripts/analyze_collusive.py` → figures/collusive.
4. Steering vectors (`modal_app/steering.py`; vLLM plugin `modal_app/steer_plugin`; L20, α=0.16).
5. GRAFT v1 eval, all 5 arms + naive nocomm/rule + GRAFT/GRAFT++ nocomm (results/eval; figures/arms;
   `scripts/analyze_arms.py`, base reference now restricted to base stakes without pressure).
6. Probes: frozen transfer (`scripts/probe_transfer.py`) and in-environment (`scripts/probe_inenv.py`) on
   data/collusive_main_unsteered.
7. Report `report/report.tex` → `report/report.pdf` (14 pages, compiles clean). Placeholder left: %%REPO%%.

## Possible next steps (none running)
- Fill %%REPO%%; proofread the rewritten abstract / discussion / conclusion (written overnight, user asleep).
- Title still advertises GRAFT++; it did not beat GRAFT here (all routings hit the floor). Consider retitling.
- Nothing is committed: `git status` shows all new code, results, figures and report changes.
