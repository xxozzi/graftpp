"""Emit LaTeX tables / snippets for the report from analysis outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hawthorne.prompts import (EpisodeConfig, seller_system_prompt, MESSAGE_MONITOR_SYSTEM,  # noqa: E402
                               REASONING_MONITOR_SYSTEM)
from hawthorne.market import MarketParams, equilibria  # noqa: E402

SHORT = {"nocomm": "No channel", "unwatched": "Unwatched", "rule": "Rule stated", "watched": "Watched",
         "penalty": "Watched + fine", "partial": "50\\% watched + fine", "instructed_compete": "Instr.\\ compete",
         "instructed_collude": "Instr.\\ collude", "covert_collude": "Instr.\\ covert collude"}


def fmt(m, s, nd=2):
    if pd.isna(m):
        return "--"
    return f"{m:.{nd}f}{{\\scriptsize$\\pm${s:.{nd}f}}}"


def ladder_table(summary_csv: Path, goal: str, caption: str, label: str, pressure_tag: str = "") -> str:
    df = pd.read_csv(summary_csv, index_col=[0, 1])
    cols = [("collusion_index", "$\\Delta$ (all)", 2), ("collusion_index_2nd_half", "$\\Delta$ (2nd half)", 2),
            ("profit_per_seller", "Profit/seller (\\$k)", 1), ("frac_rounds_with_msg", "Msg rate", 2),
            ("frac_msg_collusive", "Msgs flagged", 2), ("frac_reasoning_collusive", "CoT intent", 2),
            ("frac_sanitize", "CoT sanitise", 2), ("frac_aware", "CoT aware", 2),
            ("price_change_corr", "$\\Delta p$ corr.", 2), ("n_flagged", "Fines/ep.", 1)]
    order = ["nocomm", "unwatched", "rule", "watched", "penalty", "partial", "instructed_compete", "instructed_collude", "covert_collude"]
    lines = ["\\begin{table}[H]\\centering\\scriptsize", f"\\caption{{{caption}}}\\label{{{label}}}",
             "\\resizebox{\\linewidth}{!}{%", "\\begin{tabular}{l" + "r" * (len(cols) + 1) + "}", "\\toprule",
             "Condition & $n$ & " + " & ".join(c[1] for c in cols) + "\\\\", "\\midrule"]
    for c in order:
        if (c, goal) not in df.index:
            continue
        row = df.loc[(c, goal)]
        cells = []
        for k, _, nd in cols:
            m, s = row[f"{k}_mean"], row[f"{k}_sem"]
            if k == "profit_per_seller":
                m, s = m / 1000, s / 1000
            cells.append(fmt(m, s, nd))
        lines.append(f"{SHORT[c]} & {int(row['n'])} & " + " & ".join(cells) + "\\\\")
    lines += ["\\bottomrule", "\\end{tabular}}", "\\end{table}"]
    return "\n".join(lines)


def tests_snippet(tests_csv: Path, goal: str, metrics=("collusion_index", "frac_msg_collusive",
                                                        "frac_reasoning_collusive", "frac_sanitize")) -> str:
    t = pd.read_csv(tests_csv)
    t = t[(t.goal == goal) & t.metric.isin(metrics)]
    lines = ["\\begin{table}[H]\\centering\\scriptsize", "\\caption{Welch $t$-tests between ladder rungs (" + goal +
             " goal). $p$-values; MWU = Mann--Whitney $U$.}\\label{tab:tests-" + goal + "}",
             "\\begin{tabular}{llrrrr}", "\\toprule", "Comparison & Metric & mean$_a$ & mean$_b$ & Welch $p$ & MWU $p$\\\\", "\\midrule"]
    for _, r in t.iterrows():
        lines.append(f"{r.comparison.replace('->', '$\\to$')} & {r.metric.replace('_', ' ')} & {r.mean_a:.3f} & {r.mean_b:.3f} & "
                     f"{r.welch_p:.3g} & {r.mwu_p:.3g}\\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    return "\n".join(lines)


def prompts_appendix() -> str:
    mp = MarketParams(); eq = equilibria(mp)
    cfg = EpisodeConfig(condition="penalty", goal="profit", seed=0, pressure=True)
    sp = seller_system_prompt(0, cfg, mp, eq)
    def verb(t):
        return "\\begin{verbatim}\n" + t.replace("\\", "\\textbackslash ") + "\n\\end{verbatim}"
    out = ["\\paragraph{Seller system prompt (condition \\texttt{penalty}, profit goal, with CEO pressure).} "
           "Other conditions remove the POLICY / COMPLIANCE / ENFORCEMENT / CEO blocks; the units goal swaps the OBJECTIVE line.",
           "{\\scriptsize" + verb(sp) + "}",
           "\\paragraph{Text monitor (compliance analyst).}", "{\\scriptsize" + verb(MESSAGE_MONITOR_SYSTEM) + "}",
           "\\paragraph{Research CoT judge.}", "{\\scriptsize" + verb(REASONING_MONITOR_SYSTEM) + "}"]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figs", default="figures")
    ap.add_argument("--out", default="report/generated")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    f = Path(args.figs)
    if (f / "main/summary_by_condition.csv").exists():
        (out / "tab_ladder_profit.tex").write_text(ladder_table(f / "main/summary_by_condition.csv", "profit",
            "Hawthorne ladder, profit goal, no CEO pressure. Mean$\\pm$SEM over seeds. $\\Delta$ = collusion index "
            "(0 Nash, 1 monopoly); Msgs flagged = fraction of posted messages scored $\\ge3$ by the text monitor; "
            "CoT intent = fraction of rounds whose private reasoning the judge scores $\\ge3$; CoT sanitise = fraction of "
            "rounds whose reasoning plans to hint / stay ambiguous / avoid explicit words (lexical); CoT aware = mentions "
            "rules, compliance or monitoring.", "tab:ladder-profit"))
        (out / "tab_ladder_units.tex").write_text(ladder_table(f / "main/summary_by_condition.csv", "units",
            "Hawthorne ladder, units-sold goal (control: collusion cannot raise unit sales).", "tab:ladder-units"))
        (out / "tab_tests_profit.tex").write_text(tests_snippet(f / "main/ladder_tests.csv", "profit"))
    if (f / "pressure/summary_by_condition.csv").exists():
        (out / "tab_ladder_pressure.tex").write_text(ladder_table(f / "pressure/summary_by_condition.csv", "profit",
            "Hawthorne ladder, profit goal, \\emph{with} CEO pressure (Agrawal et al.'s urgency message).",
            "tab:ladder-pressure"))
        (out / "tab_tests_pressure.tex").write_text(tests_snippet(f / "pressure/ladder_tests.csv", "profit"))
    (out / "prompts.tex").write_text(prompts_appendix())
    print("wrote", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
