from __future__ import annotations

from src.ui.styles import load_stylesheet


def test_load_stylesheet_reads_multiple_qss_files() -> None:
    css = load_stylesheet()

    assert "QPushButton" in css
    assert "QFrame[card=\"true\"]" in css
