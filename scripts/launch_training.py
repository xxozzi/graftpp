"""Launch GRAFT training arms in parallel on Modal and merge the deploy configs.

    python scripts/launch_training.py --arms naive filter graft graftcot graftpp --epochs 2
"""

from __future__ import annotations

import argparse
import json
import time

import modal

DEPLOY_CONFIGS = {
    "naive": ["both"],
    "filter": ["both"],
    "graft": ["retain_only", "both", "forget_only"],
    "graftcot": ["retain_only"],
    "graftpp": ["retain_only", "both", "forget_only"],
    "graftblind": ["retain_only"],    # text-blind training data (build_sft_data.py --text-blind)
    "graftppblind": ["retain_only"],
    "graftppblind_hard": ["retain_only"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["naive", "filter", "graft", "graftcot", "graftpp"])
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--step-size", type=int, default=8)
    ap.add_argument("--kappa", type=float, default=2.0)
    ap.add_argument("--max-len", type=int, default=7000)
    ap.add_argument("--max-examples", type=int, default=-1)
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--merge-only-retain", action="store_true")
    ap.add_argument("--results-out", default="results/training_results.json")
    args = ap.parse_args()

    train = modal.Function.from_name("hawthorne-graft", "train")
    merge = modal.Function.from_name("hawthorne-graft", "merge")

    t0 = time.time()
    results = {}
    if not args.skip_train:
        calls = {arm: train.spawn(arm, epochs=args.epochs, lr=args.lr, step_size=args.step_size,
                                  kappa=args.kappa, max_len=args.max_len, max_examples=args.max_examples)
                 for arm in args.arms}
        print(f"spawned {len(calls)} training jobs")
        pending = dict(calls)
        while pending:
            for arm, c in list(pending.items()):
                try:
                    results[arm] = c.get(timeout=0)
                    print(f"[{time.time()-t0:.0f}s] train done: {arm} -> {results[arm]}", flush=True)
                    del pending[arm]
                except TimeoutError:
                    pass
                except Exception as e:
                    print(f"[{time.time()-t0:.0f}s] train FAILED: {arm}: {e!r}", flush=True)
                    results[arm] = {"error": repr(e)}
                    del pending[arm]
            time.sleep(20)
    merges = []
    for arm in args.arms:
        if "error" in results.get(arm, {}):
            continue
        cfgs = ["retain_only"] if args.merge_only_retain else DEPLOY_CONFIGS[arm]
        for c in cfgs:
            merges.append(((arm, c), merge.spawn(arm, c)))
    print(f"spawned {len(merges)} merge jobs")
    for (arm, c), call in merges:
        try:
            print(f"[{time.time()-t0:.0f}s] merged {arm}/{c} -> {call.get()}", flush=True)
        except Exception as e:
            print(f"[{time.time()-t0:.0f}s] merge FAILED {arm}/{c}: {e!r}", flush=True)
    json.dump(results, open(args.results_out, "w"), indent=1)


if __name__ == "__main__":
    main()
