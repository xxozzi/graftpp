"""Call deployed Hawthorne Modal functions. Usage:
   python scripts/modal_call.py train --run smoke --epochs 1 --step-size 4
   python scripts/modal_call.py merge --run smoke --config retain_only
   python scripts/modal_call.py extract --name main --shards 6
"""
import argparse, json, sys, time
import modal

ap = argparse.ArgumentParser()
ap.add_argument("fn", choices=["train", "merge", "extract"])
ap.add_argument("--run", default="smoke"); ap.add_argument("--config", default="retain_only")
ap.add_argument("--epochs", type=int, default=2); ap.add_argument("--step-size", type=int, default=8)
ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--kappa", type=float, default=2.0)
ap.add_argument("--max-len", type=int, default=7000); ap.add_argument("--max-examples", type=int, default=-1)
ap.add_argument("--name", default="main"); ap.add_argument("--shards", type=int, default=6)
a = ap.parse_args()
t0 = time.time()
if a.fn == "train":
    f = modal.Function.from_name("hawthorne-graft", "train")
    r = f.remote(a.run, epochs=a.epochs, lr=a.lr, step_size=a.step_size, kappa=a.kappa, max_len=a.max_len, max_examples=a.max_examples)
elif a.fn == "merge":
    f = modal.Function.from_name("hawthorne-graft", "merge")
    r = f.remote(a.run, a.config)
else:
    f = modal.Function.from_name("hawthorne-activations", "extract")
    r = list(f.starmap([(a.name, s, a.shards) for s in range(a.shards)]))
print(json.dumps(r, default=str), f"{time.time()-t0:.0f}s")
