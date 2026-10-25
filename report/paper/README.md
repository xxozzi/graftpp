# Paper

`paper.tex` (NeurIPS 2025 style, preprint), compiled with `latexmk -lualatex paper.tex`.

Figures, chat diagrams and every number in the text are generated from the logs in `results/`:

```bash
python scripts/export_site.py       # aggregates the logs (also feeds the website)
python scripts/paper_figs.py        # figs/*.pdf
python scripts/paper_transcripts.py # generated/t_*.tex, generated/r_*.tex
python scripts/paper_numbers.py     # generated/numbers.tex, tables
```

Fonts are not in the repository: the figures and chat diagrams use PP Neue Montreal and PP Editorial New
(Pangram Pangram, commercial licence); body text uses TeX Gyre Termes and JetBrains Mono. To compile, place
`ppneuemontreal-*.otf`, `PPEditorialNew-*.otf` and `JetBrainsMono-{Regular,Medium}.ttf` in `report/paper/fonts/`.
