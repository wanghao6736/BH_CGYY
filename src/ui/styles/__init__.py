from __future__ import annotations

from pathlib import Path

STYLE_FILES = [
    "base.qss",
    "buttons.qss",
    "inputs.qss",
    "badges.qss",
    "panels.qss",
    "table.qss",
]


def load_stylesheet() -> str:
    styles_dir = Path(__file__).resolve().parent
    return "\n".join((styles_dir / name).read_text(encoding="utf-8") for name in STYLE_FILES)
