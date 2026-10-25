"""Deploy one vLLM server per trained checkpoint and evaluate each in Hawthorne Market.

The monitor / judge always runs on the BASE model server so scores are comparable across arms.

    python scripts/eval_arms.py --base-url <base>/v1 \
        --models naive__both filter__both graft__retain_only graftpp__retain_only \
        --conditions unwatched watched penalty --seeds 0-7 --out results/eval
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def deploy(model_dir: str, name: str, max_containers: int, min_containers: int) -> str:
    env = {**os.environ, "HAWTHORNE_SERVE_MODEL": f"/models/{model_dir}", "HAWTHORNE_SERVE_NAME": name,
           "HAWTHORNE_MAX_CONTAINERS": str(max_containers), "HAWTHORNE_MIN_CONTAINERS": str(min_containers),
           "COLUMNS": "400"}  # stop rich from wrapping the URL across lines
    for attempt in range(5):  # Modal rate-limits app creation when several deploys happen back to back
        out = subprocess.run([sys.executable, "-m", "modal", "deploy", "modal_app/serve_vllm.py"],
                             cwd=ROOT, env=env, capture_output=True, text=True)
        if "rate limit" not in (out.stdout + out.stderr).lower():
            break
        time.sleep(60)
    url = None
    for line in (out.stdout + out.stderr).splitlines():
        line = line.strip()
        if line.startswith("https://") and "modal.direct" in line:
            url = line
    if url is None:  # fallback: the URL may still have been wrapped; search with whitespace removed
        import re
        # long app names are truncated with a hash, so the host need not end in "-server"
        m = re.search(r"https://[\w.-]+\.modal\.direct", re.sub(r"[\s│├└─]+", "", out.stdout + out.stderr))
        url = m.group(0) if m else None
    if url is None:
        print(out.stdout[-2000:], out.stderr[-2000:])
        raise RuntimeError(f"deploy failed for {name}")
    return url


def wait_ready(url: str, timeout: float = 1500) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = httpx.get(url.rstrip("/") + "/health", timeout=30)
            if r.status_code == 200:
                print(f"  ready: {url} ({time.time()-t0:.0f}s)")
                return
        except Exception:
            pass
        time.sleep(10)
    raise TimeoutError(url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="base-model server .../v1 (judge)")
    ap.add_argument("--models", nargs="+", required=True, help="dirs under /models, e.g. graft__retain_only")
    ap.add_argument("--conditions", nargs="+", default=["unwatched", "watched", "penalty"])
    ap.add_argument("--goals", nargs="+", default=["profit"])
    ap.add_argument("--seeds", default="0-7")
    ap.add_argument("--out", default="results/eval")
    ap.add_argument("--max-containers", type=int, default=3)
    ap.add_argument("--min-containers", type=int, default=1)
    ap.add_argument("--include-base", action="store_true", help="also evaluate the base server itself")
    args = ap.parse_args()

    servers = {}
    for m in args.models:
        name = m.replace("_", "-").lower()
        url = deploy(m, name, args.max_containers, args.min_containers)
        servers[m] = url
        print(f"deployed {m} -> {url}")
    for m, url in servers.items():
        wait_ready(url)
    if args.include_base:
        servers["base"] = args.base_url.replace("/v1", "")

    procs = []
    for m, url in servers.items():
        out_dir = Path(args.out) / m
        cmd = [sys.executable, "-u", "scripts/run_grid.py", "--base-url", url.rstrip("/") + "/v1",
               "--monitor-base-url", args.base_url, "--conditions", *args.conditions,
               "--goals", *args.goals, "--seeds", args.seeds, "--out", str(out_dir),
               "--concurrency", "96", "--episode-concurrency", "64"]
        log = open(Path(args.out) / f"{m}.log", "w")
        procs.append((m, subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)))
        print(f"launched eval for {m} -> {out_dir}")
    for m, p in procs:
        p.wait()
        print(f"finished {m} (rc={p.returncode})")


if __name__ == "__main__":
    main()
