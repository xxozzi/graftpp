"""Combine several activation dirs (records/meta/acts) into one for probes.py."""
import shutil, sys, glob
from pathlib import Path
import pandas as pd
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
metas = []
with open(out / "records.jsonl", "w") as fo:
    for d in sys.argv[2:]:
        d = Path(d); name = d.name
        for f in glob.glob(str(d / "acts_*.npz")):
            shutil.copy(f, out / f"acts_{name}_{Path(f).stem.split('_')[-1]}.npz")
        metas.append(pd.read_csv(d / "meta.csv"))
        fo.write(open(d / "records.jsonl").read())
pd.concat(metas, ignore_index=True).to_csv(out / "meta.csv", index=False)
print("merged ->", out, sum(len(m) for m in metas), "records")
