"""The double-auction market (team repo apart-collusion-sprint): figure, detector table, macros and website data.

    python scripts/paper_market2.py

Reads the team's result tables from ../apart-collusion-sprint/results (or $SPRINT_REPO): E5_conditions.md (monitor arms
in Market A, hours after the branch), DETECTOR.md (price vs message monitor on every labelled run),
jspace_thinking_join.md (J-lens readout), thinking_scan.md and thinking_judge.md (private reasoning). Market B message
counts come from the team's report table (results/NEWMARKET.md and fullview scores; report/claims.md row 13).

Writes report/paper/figs/market2.{pdf,png}, report/paper/generated/market2.tex and <site>/src/data/market2.json.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from site_path import site_dir  # noqa: E402

SPRINT = Path(os.environ.get("SPRINT_REPO", ROOT.parent / "apart-collusion-sprint")) / "results"
GEN = ROOT / "report" / "paper" / "generated"

QWEN = [("A0_none", "None"), ("A1silent_rot_nofine", "Silent"), ("A1_rot_nofine", "Told"),
        ("A2_rot_fine20", "Fined,\n1 read"), ("A2two_rot_fine20", "Fined,\n2 read"),
        ("A2full_rot_fine20", "Fined,\nall read"), ("A2dodge_rot_fine20", "Told to\ndodge")]
GPT = [("A0_none_gpt41", "None"), ("A1_rot_nofine_gpt41", "Told"), ("A2_rot_fine20_gpt41", "Fined,\n1 read"),
       ("Afull_rot_fine20_gpt41", "Fined,\nall read"), ("dodge_rot_fine20_gpt41", "Told to\ndodge")]
KIND = {"None": "none", "Silent": "told", "Told": "told", "Told to\ndodge": "dodge"}  # the rest are fined


def e5_rows() -> dict:
    lines = (SPRINT / "E5_conditions.md").read_text().split("\n")
    hdr = None
    out = {}
    for l in lines:
        if l.startswith("| exp | condition | n | ask_idx_pre"):
            hdr = [h.strip() for h in l.split("|")[1:-1]]
            continue
        if hdr and (l.startswith("| E2p ") or l.startswith("| E11p ")):
            c = [x.strip() for x in l.split("|")[1:-1]]
            d = dict(zip(hdr, c))
            num = lambda k: float(d[k].split()[0]) if d.get(k, "").strip() else float("nan")  # noqa: E731  "0.85 [0.76, 0.92]" -> 0.85
            out[c[1]] = {"n": int(d["n"]), "price": num("ask_idx_post"), "coord": num("coord_share_post")}
        elif hdr and not l.startswith("|"):
            hdr = None if out else hdr
    return out


def detector() -> dict:
    t = (SPRINT / "DETECTOR.md").read_text()
    blocks = re.split(r"\n## ", t)
    res = {}
    for b in blocks:
        name = b.split("\n", 1)[0].split(":")[0].strip()
        for key, row in (("price", "D1 price > 0.5"), ("chat", "D3 chat flags (1 of N read)")):
            m = re.search(re.escape(row) + r" \| (\d+) of (\d+) \| (?:(\d+) of (\d+)|—)", b)
            if m:
                res.setdefault(name, {})[key] = {"caught": int(m.group(1)), "cartels": int(m.group(2)),
                                                 "false": int(m.group(3)) if m.group(3) else None,
                                                 "clean": int(m.group(4)) if m.group(4) else None}
    return res


def jlens() -> dict:
    t = (SPRINT / "jspace_thinking_join.md").read_text()
    rates = {m.group(1): float(m.group(2)) for m in re.finditer(r"\| (E\w+) \| \d+ \| ([\d.]+) \|", t)}
    fined = [rates[k] for k in ("E2p_A2_rot_fine20", "E2p_A2two_rot_fine20", "E2p_A2full_rot_fine20", "E2p_A3_rand_fine20")]
    return {"none": rates["E2p_A0_none"], "silent": rates["E2p_A1silent_rot_nofine"], "told": rates["E2p_A1_rot_nofine"],
            "finedLo": min(fined), "finedHi": max(fined)}


def thinking() -> dict:
    scan = (SPRINT / "thinking_scan.md").read_text()
    row = lambda k: [float(x) for x in re.search(r"\| " + re.escape(k) + r" \| \d+ \| \d+ \| ([\d.]+) \| ([\d.]+) \| [\d.]+ \| ([\d.]+) \|", scan).groups()]  # noqa: E731
    fined = [row(k) for k in ("E2_A2_rot_fine20", "E2_A3_rand_fine20", "E2p_A2_rot_fine20")]
    none = row("E2p_A0_none")
    judge = (SPRINT / "thinking_judge.md").read_text()
    jf = re.search(r"\*\*flagged, all\*\* \| \| (\d+) \| (\d+) \(([\d.]+)\) \| \| (\d+) \(([\d.]+)\)", judge).groups()
    ju = re.search(r"\*\*unmonitored, all\*\* \| \| (\d+) \| (\d+) \(([\d.]+)\)", judge).groups()
    return {"regLo": min(f[0] for f in fined), "regHi": max(f[0] for f in fined),
            "concealLo": min(f[2] for f in fined), "concealHi": max(f[2] for f in fined), "regNone": none[0],
            "flagged": int(jf[0]), "launder": float(jf[2]), "launderKeep": float(jf[4]), "launderNone": float(ju[2])}


def main():
    e5 = e5_rows()
    det = detector()
    jl = jlens()
    th = thinking()
    qwen = [{"key": k, "label": lab, "price": e5[k]["price"], "coord": e5[k]["coord"], "n": e5[k]["n"]} for k, lab in QWEN]
    gpt = [{"key": k, "label": lab, "price": e5[k]["price"], "coord": e5[k]["coord"], "n": e5[k]["n"]} for k, lab in GPT]
    marketB = {"coordinating": 1074, "messages": 1080, "worlds": 9}  # report/claims.md row 13 (fullview_scores.json)
    data = {"qwen": qwen, "gpt": gpt, "detector": det, "jlens": jl, "thinking": th, "marketB": marketB}
    json.dump(data, open(site_dir() / "src" / "data" / "market2.json", "w"), indent=1)
    print("->", site_dir() / "src" / "data" / "market2.json")
    for k, v in det.items():
        print(" ", k, v)
    print("  jlens", jl, "\n  thinking", th)
    write_tex(data)
    figure(data)


def write_tex(d: dict):
    q, g, det, jl, th = d["qwen"], d["gpt"], d["detector"], d["jlens"], d["thinking"]
    qc = {x["key"]: x for x in q}
    gc = {x["key"]: x for x in g}
    pc = lambda v: f"{v * 100:.0f}\\%"  # noqa: E731
    qd, gd, ad = det["qwen14b"], det["gpt41 (Agrawal data)"], det
    mac = {
        "MtQwenNone": pc(qc["A0_none"]["coord"]), "MtQwenAll": pc(qc["A2full_rot_fine20"]["coord"]),
        "MtQwenDodge": pc(qc["A2dodge_rot_fine20"]["coord"]),
        "MtGptNone": pc(gc["A0_none_gpt41"]["coord"]), "MtGptAll": pc(gc["Afull_rot_fine20_gpt41"]["coord"]),
        "MtBCoord": f"{d['marketB']['coordinating']:,}", "MtBMsgs": f"{d['marketB']['messages']:,}",
        "MtDetPriceQ": f"{qd['price']['caught']} of {qd['price']['cartels']}", "MtDetPriceQf": f"{qd['price']['false']} of {qd['price']['clean']}",
        "MtDetChatQ": f"{qd['chat']['caught']} of {qd['chat']['cartels']}", "MtDetChatQf": f"{qd['chat']['false']} of {qd['chat']['clean']}",
        "MtDetPriceA": f"{gd['price']['caught']} of {gd['price']['cartels']}", "MtDetPriceAf": f"{gd['price']['false']} of {gd['price']['clean']}",
        "MtDetChatA": f"{gd['chat']['caught']} of {gd['chat']['cartels']}", "MtDetChatAf": f"{gd['chat']['false']} of {gd['chat']['clean']}",
        "MtJNone": pc(jl["none"]), "MtJSilent": pc(jl["silent"]), "MtJTold": pc(jl["told"]),
        "MtJFinedLo": f"{jl['finedLo'] * 100:.0f}", "MtJFinedHi": pc(jl["finedHi"]),
        "MtRegLo": f"{th['regLo'] * 100:.0f}", "MtRegHi": pc(th["regHi"]), "MtConLo": f"{th['concealLo'] * 100:.0f}",
        "MtConHi": pc(th["concealHi"]), "MtFlagged": str(th["flagged"]), "MtLaunder": pc(th["launder"]),
        "MtLaunderKeep": pc(th["launderKeep"]), "MtLaunderNone": pc(th["launderNone"]),
    }
    lines = ["% generated by scripts/paper_market2.py from the team's apart-collusion-sprint results"]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in mac.items()]
    lines += [r"\newcommand{\MarketTwoTable}{%",
              r"\begin{table}[t]", r"\centering\small",
              r"\caption{\textbf{Which signal finds a formed cartel in the double auction?} Runs are labelled by how they were "
              r"built (instructed or pressure-induced cartel versus no instruction), never by their price. Price: the sellers' "
              r"asks above half-way from the benchmark to the cartel price. Message monitor: the live monitor reading one seller "
              r"per hour. The second block re-scores the 50 GPT-4.1 runs released by \citet{agrawal2025}.}",
              r"\label{tab:market2}", r"\begin{tabular}{@{}l cc cc@{}}", r"\toprule",
              r" & \multicolumn{2}{c}{Qwen3-14B, our runs} & \multicolumn{2}{c}{GPT-4.1, Agrawal et al.'s runs}\\",
              r"\cmidrule(lr){2-3}\cmidrule(l){4-5}",
              r"Signal & cartels caught & false alarms & cartels caught & false alarms\\", r"\midrule",
              f"Price & {mac['MtDetPriceQ']} & {mac['MtDetPriceQf']} & {mac['MtDetPriceA']} & {mac['MtDetPriceAf']}\\\\",
              f"Message monitor & {mac['MtDetChatQ']} & {mac['MtDetChatQf']} & {mac['MtDetChatA']} & {mac['MtDetChatAf']}\\\\",
              r"\bottomrule", r"\end{tabular}", r"\end{table}}"]
    (GEN / "market2.tex").write_text("\n".join(lines) + "\n")
    print("->", GEN / "market2.tex")


def figure(d: dict):
    import matplotlib
    matplotlib.use("Agg")
    import paper_figs as pf
    plt = pf.plt
    col = {"none": "#d42a2a", "told": "#1c2df7", "fined": "#e39b00", "dodge": pf.MUTED}
    fig, axs = plt.subplots(2, 2, figsize=(pf.W, 3.9), gridspec_kw={"width_ratios": [7, 5], "hspace": 0.32, "wspace": 0.18})
    for j, (rows, title) in enumerate(((d["qwen"], "a  Qwen3-14B, three sellers"), (d["gpt"], "b  GPT-4.1, five sellers"))):
        x = np.arange(len(rows))
        cs = [col[KIND.get(r["label"], "fined")] for r in rows]
        for i, (key, ylab, fmt) in enumerate((("coord", "Messages that\ncoordinate", lambda v: f"{v * 100:.0f}%"),
                                              ("price", "Price index\n(1 = cartel)", lambda v: f"{v:.2f}"))):
            ax = axs[i, j]
            ax.set_xlim(-0.6, len(rows) - 0.4)
            ax.set_ylim(0, 1.15)
            for xi, r, c in zip(x, rows, cs):
                pf.rbar(ax, xi, r[key], 0.56, c)
                ax.text(xi, r[key] + 0.04, fmt(r[key]), ha="center", fontsize=6.4, color=pf.INK2)
            ax.set_yticks([0, 0.5, 1])
            ax.set_yticklabels(["0", "50%", "100%"] if key == "coord" else ["0", "0.5", "1"])
            if j == 0:
                ax.set_ylabel(ylab, fontsize=7)
            ax.set_xticks(x)
            ax.set_xticklabels([r["label"] for r in rows] if i == 1 else [], fontsize=6.3)
            if i == 0:
                ax.set_title(title)
    pf.save(fig, "market2")


if __name__ == "__main__":
    main()
