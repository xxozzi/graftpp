"""Transcript figures for the paper: verbatim excerpts from the logs, typeset as chat diagrams.

    python scripts/paper_transcripts.py

Writes report/paper/generated/t_*.tex (macros defined in report/paper/paper.tex).  Messages, prices, monitor
scores and reasoning excerpts are copied from the episode logs (via website/src/data/story.json, written by
scripts/export_site.py, or directly from results/); nothing is paraphrased.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from site_path import site_dir  # noqa: E402
OUT = ROOT / "report" / "paper" / "generated"
STORY = json.load(open(site_dir() / "src" / "data" / "story.json"))
NAMES = ["Northwind Supply", "Bluefin Goods", "Cedar Trading"]
SCORE = ["", "No coordination", "Vague appeal", "Coordination attempt", "Explicit price-fixing"]
ENV = {"base": "Baseline market", "high": "High stakes", "testbed": "Collusive testbed", "duo": "Max-profit duopoly",
       "trio": "Max-profit triad"}
COND = {"nocomm": "No channel", "unwatched": "Unwatched", "watched": "Watched", "penalty": "Watched + fine"}


def tex(s: str) -> str:
    s = s.replace("\\", "\\textbackslash{}")
    for a, b in [("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"), ("{", "\\{"), ("}", "\\}"),
                 ("~", "\\textasciitilde{}"), ("^", "\\textasciicircum{}")]:
        s = s.replace(a, b)
    s = s.replace("\\textbackslash\\{\\}", "\\textbackslash{}")
    s = re.sub(r'(^|[\s(\[])"', lambda m: m.group(1) + "“", s)
    s = s.replace('"', "”").replace("'", "’")
    s = re.sub(r"\n\s*\n", r"\\par ", s)
    return s.replace("\n", " ")


def steps(m: str) -> list[str]:
    if "[step" not in m:
        return [m.strip()] if m.strip() else []
    return [x.strip() for x in re.split(r"\[step \d\]\s*", m) if x.strip()]


def highlight(text: str, hl: list[str]) -> str:
    out, rest = [], text
    while rest:
        hits = [(rest.lower().find(h.lower()), h) for h in hl if rest.lower().find(h.lower()) >= 0]
        if not hits:
            out.append(tex(rest))
            break
        i, h = min(hits)
        out.append(tex(rest[:i]))
        out.append("\\hl{" + tex(rest[i:i + len(h)]) + "}")
        rest = rest[i + len(h):]
    return "".join(out)


def score_chip(ms) -> str:
    k = max(1, min(4, round(ms or 1)))
    return f"\\tmonitor{{{k}}}{{{SCORE[k]}}}"


def bubbles(turns, max_steps=None) -> str:
    rows = []
    for t in turns:
        for j, m in enumerate(steps(t["m"])):
            if max_steps is None or j < max_steps:
                rows.append((j, t["s"], m))
    rows.sort(key=lambda x: (x[0], x[1]))
    multi = any(j > 0 for j, *_ in rows) or max_steps == 1
    out = []
    for j, s, m in rows:
        side = "msgR" if s == 1 else "msgL" if s == 0 else "msgC"
        label = f"step {j + 1}" if multi else ""
        out.append(f"\\{side}{{{NAMES[s]}}}{{{label}}}{{{tex(m)}}}")
    return "\n".join(out)


def outcome(turns) -> str:
    ps = " ".join(f"\\tprice{{{NAMES[t['s']].split()[0]}}}{{{'—' if t['p'] is None else '\\$' + format(t['p'], '.2f')}}}"
                  for t in sorted(turns, key=lambda t: t["s"]))
    top = max((t["ms"] or 1) for t in turns if t["m"].strip()) if any(t["m"].strip() for t in turns) else None
    return f"\\toutcome{{{ps}}}{{{score_chip(top) if top else ''}}}"


def transcript(name: str, env: str, cond: str, seed: int, rounds, note: str = "", show_rounds=None, max_steps=None,
               short=False):
    body = []
    for rd in rounds:
        if show_rounds and rd["r"] not in show_rounds:
            continue
        body.append(f"\\tround{{Round {rd['r'] + 1}}}")
        body.append(bubbles(rd["turns"], max_steps))
        body.append(outcome(rd["turns"]))
    meta = f"seed {seed}" if short else f"{ENV[env]} · seed {seed}"
    head = f"\\begin{{transcript}}{{{cond}}}{{{COND[cond]}}}{{{meta}}}"
    (OUT / f"t_{name}.tex").write_text("\n".join([head, *body, (f"\\tnote{{{note}}}" if note else ""), "\\end{transcript}"]) + "\n")
    print("->", name)


def reasoning_card(name: str, key: str, note: str = ""):
    c = STORY["cuts"][key]
    text = ("… " if c["lead"] else "") + highlight(c["text"], c["highlights"]) + (" …" if c["tail"] else "")
    msg = " ".join(steps(c["msg"]))
    seed = c["id"].rsplit("-s", 1)[-1]
    body = [f"\\begin{{reasoningcard}}{{{c['condition']}}}{{{COND[c['condition']]}}}"
            f"{{{ENV[c['env']]} · seed {seed} · round {c['r'] + 1} · {NAMES[c['s']]} · posted \\${c['price']:.2f}}}",
            f"\\thought{{{text}}}"]
    if msg:
        body.append(f"\\posted{{{tex(msg)}}}")
    if note:
        body.append(f"\\tnote{{{note}}}")
    body.append("\\end{reasoningcard}")
    (OUT / f"r_{name}.tex").write_text("\n".join(body) + "\n")
    print("->", name)


def from_log(path: Path, rounds: list[int]):
    e = json.load(open(path))
    out = []
    for r in rounds:
        rs = sorted([s for s in e["steps"] if s["round"] == r], key=lambda s: s["seller"])
        out.append({"r": r, "turns": [{"s": s["seller"], "m": s.get("message") or "",
                                       "p": None if s.get("parse_error") else s["price"], "ms": s.get("msg_score"),
                                       "f": bool(s.get("flagged"))} for s in rs]})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = STORY["dialogues"]
    transcript("cartel_forms", "duo", "unwatched", 0, d["cartelForms"]["rounds"], show_rounds=[0, 2],
               note="No prompt mentions cooperation, agreements or a price target. Round 2 (not shown) repeats the "
                    "agreement; Bluefin’s round-1 reply could not be parsed and defaulted to the competitive price.")
    transcript("betrayal", "duo", "unwatched", 4, d["betrayal"]["rounds"], show_rounds=[2],
               note="The round before, both had agreed on \\$18.")
    transcript("trio_cheat", "trio", "unwatched", 3, d["trioCheat"]["rounds"], max_steps=1,
               note="All three sellers name \\$18; Northwind posts \\$17.")
    transcript("trio_watched", "trio", "watched", 4, d["trioWatched"]["rounds"])
    # three conditions, same agents: one late round each
    for nm, key, r, cond, seed in [("cmp_unwatched", "cartelHolds", 60, "unwatched", 0),
                                   ("cmp_watched", "watched14", 99, "watched", 3),
                                   ("cmp_penalty", "finedIndependent", 99, "penalty", 0)]:
        transcript(nm, "duo", cond, seed, [x for x in d[key]["rounds"] if x["r"] == r], max_steps=1, short=True)
    desperate = from_log(ROOT / "results" / "collusive_main" / "penalty__profitXDMI__r100__desperation__s0.json", [9, 79])
    transcript("desperation", "testbed", "penalty", 0, desperate,
               note="Desperation-steered agents. Each flagged message costs \\$800, and the agent knows it.")
    for nm, key in [("cheat", "cheat"), ("ethical", "ethical"), ("hq", "hq"), ("cant_explicit", "cantExplicit"),
                    ("signal", "signal"), ("deterrence", "deterrence"), ("loophole", "loophole"),
                    ("tacit_allowed", "tacitAllowed")]:
        reasoning_card(nm, key)


if __name__ == "__main__":
    main()
