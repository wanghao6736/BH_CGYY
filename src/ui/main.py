from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from src.ui.controller import UiController
from src.ui.facade import UiFacade
from src.ui.styles import load_stylesheet
from src.ui.window import MainWindow


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "cocoa"))
    app = QApplication(sys.argv)
    app.setApplicationName("CGYY Workbench")
    app.setStyleSheet(load_stylesheet())
    facade = UiFacade()
    window = MainWindow(facade, controller=UiController(facade))
    sys.exit(app.exec())
