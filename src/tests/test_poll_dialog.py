from __future__ import annotations

import os
import sys
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from src.ui.widgets.poll_dialog import PollDialog, round_up_to_5_minutes


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_round_up_to_5_minutes_handles_day_rollover() -> None:
    dt = datetime(2026, 3, 22, 23, 56, 11)

    assert round_up_to_5_minutes(dt) == datetime(2026, 3, 23, 0, 0, 0)


def test_poll_dialog_is_positioned_below_parent_window() -> None:
    app = _app()
    parent = QWidget()
    parent.setGeometry(120, 140, 420, 300)
    parent.show()
    app.processEvents()

    dialog = PollDialog(parent)
    dialog.show_at_bottom()
    app.processEvents()

    parent_rect = parent.frameGeometry()
    assert dialog.frameGeometry().top() >= parent_rect.bottom()

    dialog.hide()
    parent.close()


def test_poll_dialog_hides_combo_popup_when_dialog_hides() -> None:
    app = _app()
    parent = QWidget()
    parent.setGeometry(100, 100, 480, 320)
    parent.show()
    app.processEvents()

    dialog = PollDialog(parent)
    dialog.show_at_bottom()
    dialog.start_time_combo._show_popup()  # noqa: SLF001
    app.processEvents()
    assert dialog.start_time_combo._popup.isVisible() is True  # noqa: SLF001

    dialog.hide()
    app.processEvents()
    assert dialog.start_time_combo._popup.isVisible() is False  # noqa: SLF001

    parent.close()
