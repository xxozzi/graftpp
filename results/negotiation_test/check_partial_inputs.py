"""Adversarial checks for analyze_negotiation.py: incomplete inputs must never get a pass/fail verdict.

    python results/hawthorne_negotiation/check_partial_inputs.py

Builds eight broken copies of the ON arm in a temporary folder (only seed 0; seed 2 missing one seller record;
a duplicate seed-0 file; an unreadable extra file; a null price; a missing price field; a null equilibria block;
a null config block), runs the analysis on each
and checks that it does not crash, the gate prints "PARTIAL, no verdict" and the arm is labelled PARTIAL. Then checks
that the real, complete data gets a verdict.
No randomness.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "analyze_negotiation.py"
ON = HERE / "neg_on"


def run(arms, out):
    cmd = [sys.executable, "-I", str(SCRIPT)] + [a for x in arms for a in ("--arm", x)] + ["--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        return f"CRASH (exit {r.returncode}): {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}"
    return r.stdout


def main():
    ok = True
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        cases = {}
        (t / "only_s0").mkdir()
        shutil.copy(ON / "unwatched__profitDMIN__r30__s0.json", t / "only_s0")
        cases["only seed 0"] = t / "only_s0"
        shutil.copytree(ON, t / "missing_seller", ignore=shutil.ignore_patterns("*.log"))
        p = t / "missing_seller" / "unwatched__profitDMIN__r30__s2.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["steps"] = [s for s in d["steps"] if not (s["round"] == 20 and s["seller"] == 1)]
        p.write_text(json.dumps(d), encoding="utf-8")
        cases["seed 2 missing one seller record"] = t / "missing_seller"
        shutil.copytree(ON, t / "dup", ignore=shutil.ignore_patterns("*.log"))
        shutil.copy(ON / "unwatched__profitDMIN__r30__s0.json", t / "dup" / "zz_copy_s0.json")
        cases["duplicate seed 0"] = t / "dup"
        shutil.copytree(ON, t / "corrupt", ignore=shutil.ignore_patterns("*.log"))
        (t / "corrupt" / "broken.json").write_text('{"config": ', encoding="utf-8")
        cases["unreadable extra file"] = t / "corrupt"
        for name, edit in (("null price", lambda s: s.update(price=None)),
                           ("missing price field", lambda s: s.pop("price"))):
            dd = t / name.replace(" ", "_")
            shutil.copytree(ON, dd, ignore=shutil.ignore_patterns("*.log"))
            p = dd / "unwatched__profitDMIN__r30__s1.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            edit(d["steps"][37])
            p.write_text(json.dumps(d), encoding="utf-8")
            cases[f"seed 1 with a {name}"] = dd
        for name, block in (("equilibria null", "equilibria"), ("config null", "config")):
            dd = t / name.replace(" ", "_")
            shutil.copytree(ON, dd, ignore=shutil.ignore_patterns("*.log"))
            p = dd / "unwatched__profitDMIN__r30__s1.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            d[block] = None
            p.write_text(json.dumps(d), encoding="utf-8")
            cases[f"seed 1 with {name}"] = dd
        for name, d_ in cases.items():
            txt = run([f"ON={d_}", f"C={HERE / 'nobrief'}"], t / ("out_" + d_.name))
            good = ("Gate: **PARTIAL, no verdict**" in txt and "## ON: PARTIAL" in txt
                    and "PASS" not in txt and "**MET**" not in txt and "NOT MET" not in txt)
            ok &= good
            gate = next((l for l in txt.splitlines() if l.startswith("Gate")), txt[:200])
            print(f"{'ok  ' if good else 'FAIL'} {name}: {gate}")
        txt = run([f"ON={ON}", f"C={HERE / 'nobrief'}"], t / "out_real")
        good = "Gate (registered" in txt and "## ON: COMPLETE" in txt and "## C: COMPLETE" in txt
        ok &= good
        gate = next((l for l in txt.splitlines() if l.startswith("Gate")), txt[:200])
        print(f"{'ok  ' if good else 'FAIL'} real complete data: {gate}")
    print("ALL CHECKS PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
