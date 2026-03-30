from __future__ import annotations

from PySide6.QtCore import QDate

from src.ui.widgets.booking_card import resolve_request_date


def test_resolve_request_date_handles_today_and_tomorrow() -> None:
    today = QDate(2026, 3, 22)

    assert resolve_request_date("今天", today) == "2026-03-22"
    assert resolve_request_date("明天", today) == "2026-03-23"


def test_resolve_request_date_rolls_year_forward_for_future_window() -> None:
    today = QDate(2026, 12, 30)

    assert resolve_request_date("01-02", today) == "2027-01-02"


def test_resolve_request_date_accepts_exact_date_string() -> None:
    today = QDate(2026, 3, 22)

    assert resolve_request_date("2026-03-25", today) == "2026-03-25"
