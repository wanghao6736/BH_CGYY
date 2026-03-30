from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import QApplication, QDateEdit, QTimeEdit

from src.ui.widgets.action_bar import ActionBar
from src.ui.widgets.booking_card import BookingCard
from src.ui.widgets.expandable_details_panel import ExpandableDetailsPanel
from src.ui.widgets.panel_dialog import PanelDialog
from src.ui.widgets.top_toolbar import TopToolbar


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_top_toolbar_exposes_profile_and_panel_controls() -> None:
    _app()
    bar = TopToolbar()

    assert bar.profile_combo is not None
    assert bar.panel_button.text() == "面板"


def test_booking_card_uses_dedicated_date_and_time_controls() -> None:
    _app()
    card = BookingCard()

    assert isinstance(card.date_edit, QDateEdit)
    assert isinstance(card.time_edit, QTimeEdit)


def test_booking_card_exposes_compact_request_values() -> None:
    _app()
    card = BookingCard()
    card.date_edit.setDate(QDate(2026, 3, 22))
    card.time_edit.setTime(QTime(18, 0))
    card.slot_spin.setValue(2)

    values = card.current_request_values()

    assert values["date"] == "2026-03-22"
    assert values["start_time"] == "18:00"
    assert values["slot_count"] == 2
    assert set(values) >= {"date", "start_time", "slot_count", "venue_site_id", "mode"}


def test_action_bar_exposes_homepage_actions() -> None:
    _app()
    bar = ActionBar()

    assert bar.reserve_button.text() == "立即预约"
    assert "轮询" in bar.poll_button.text()


def test_expandable_details_panel_starts_collapsed() -> None:
    _app()
    panel = ExpandableDetailsPanel()

    assert panel.is_expanded() is False


def test_panel_dialog_hosts_details_and_settings_tabs() -> None:
    _app()
    dialog = PanelDialog()

    assert dialog.tabs.count() >= 2
