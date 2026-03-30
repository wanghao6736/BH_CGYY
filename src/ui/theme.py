from __future__ import annotations

from src.ui.styles import load_stylesheet

# Compatibility shim for modules still importing APP_QSS.
APP_QSS = load_stylesheet()
