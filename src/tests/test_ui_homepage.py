from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.animations import build_expand_animation
from src.ui.state import (BoardCell, BoardRow, BoardState, BoardStatus,
                          PollingState, PollingStatus, ProfileOption,
                          SelectionState, SessionState, SessionStatus)
from src.ui.window import MainWindow


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class FakeFacade:
    def list_profiles(self):
        return [
            ProfileOption(
                name="default",
                display_name="默认用户",
                auth_source="self",
                sso_source="self",
            )
        ]


class FakeController:
    pass


def make_authed_session() -> SessionState:
    return SessionState(
        profile_name="default",
        display_name="默认用户",
        status=SessionStatus.AUTHENTICATED,
    )


def make_running_polling_state() -> PollingState:
    return PollingState(
        status=PollingStatus.RUNNING,
        interval_sec=8,
        last_checked_at="14:32:08",
        last_message="最近无可用时段",
    )


def make_board_state() -> BoardState:
    return BoardState(
        status=BoardStatus.READY,
        profile_name="default",
        venue_site_id=57,
        venue_label="2号馆 / 羽毛球",
        date="2026-03-22",
        slot_count=2,
        rows=[
            BoardRow(
                space_id=101,
                space_name="A1",
                cells=[
                    BoardCell(
                        space_id=101,
                        space_name="A1",
                        time_id=1,
                        begin_time="18:00",
                        end_time="18:30",
                        label="18:00",
                        status_text="空闲",
                        selectable=True,
                        is_available=True,
                    )
                ],
            )
        ],
        time_headers=["18:00"],
    )


def make_selection() -> SelectionState:
    return SelectionState(
        space_id=101,
        space_name="A1",
        start_time="18:00",
        end_time="19:00",
        slot_count=2,
    )


def test_homepage_defaults_to_card_first_layout() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert window.top_toolbar is not None
    assert window.booking_card is not None
    assert window.action_bar is not None
    assert window.details_panel.is_expanded() is False
    window.close()


def test_homepage_exposes_reserve_and_poll_actions() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert window.action_bar.reserve_button.text() == "立即预约"
    assert "轮询" in window.action_bar.poll_button.text()
    window.close()


def test_query_does_not_auto_expand_details_panel() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())
    window.apply_session_state(make_authed_session())

    window.handle_board_loaded(1, make_board_state())

    assert window.details_panel.is_expanded() is False
    window.close()


def test_homepage_shows_compact_polling_summary() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert window.polling_summary is not None
    assert window.polling_summary.isVisible() is True
    window.close()


def test_query_is_disabled_while_polling_is_running() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())
    window.apply_session_state(make_authed_session())
    window.apply_board_state(make_board_state())
    window.apply_selection_state(make_selection())

    window.apply_polling_state(make_running_polling_state())

    assert window.action_bar.query_button.isEnabled() is False
    window.close()


def test_expand_details_button_toggles_details_panel() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    window.action_bar.details_button.click()

    assert window.details_panel.is_expanded() is True
    window.close()


def test_expand_animation_helper_returns_animation_group() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    animation = build_expand_animation(window.details_panel.content_container, expand=True)

    assert animation is not None
    window.close()
