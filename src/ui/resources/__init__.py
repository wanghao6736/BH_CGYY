from __future__ import annotations

from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent

APP_ICON_PNG = RESOURCES_DIR / "app_icon.png"
APP_ICON_ICNS = RESOURCES_DIR / "app_icon.icns"


def app_icon_path() -> Path:
    """Return the best available app-icon path for the current platform."""
    import sys

    if sys.platform == "darwin" and APP_ICON_ICNS.exists():
        return APP_ICON_ICNS
    return APP_ICON_PNG
