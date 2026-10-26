"""Where the website lives: $HAWTHORNE_SITE, else ../hawthorne-site next to this repository, else ./website."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def site_dir() -> Path:
    if os.environ.get("HAWTHORNE_SITE"):
        return Path(os.environ["HAWTHORNE_SITE"]).expanduser().resolve()
    sibling = ROOT.parent / "hawthorne-site"
    return sibling if (sibling / "package.json").exists() else ROOT / "website"
