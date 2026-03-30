from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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
        return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]


class FakeController:
    pass


class RejectingPollController:
    def request_start_polling(self, query):  # pragma: no cover - simple stub
        return None


def make_unauth_session() -> SessionState:
    return SessionState(
        profile_name="default",
        display_name="默认用户",
        status=SessionStatus.UNAUTHENTICATED,
    )


def make_authed_session() -> SessionState:
    return SessionState(
        profile_name="default",
        display_name="默认用户",
        status=SessionStatus.AUTHENTICATED,
    )


def make_selection() -> SelectionState:
    return SelectionState(
        space_id=101,
        space_name="A1",
        start_time="18:00",
        end_time="19:00",
        slot_count=2,
    )


def make_board_state(*, date: str = "2026-03-22") -> BoardState:
    return BoardState(
        status=BoardStatus.READY,
        profile_name="default",
        venue_site_id=57,
        venue_label="2号馆 / 羽毛球",
        date=date,
        slot_count=2,
        start_time="18:00",
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


def make_running_polling_state() -> PollingState:
    return PollingState(
        status=PollingStatus.RUNNING,
        interval_sec=8,
        last_checked_at="14:32:08",
        last_message="最近无可用时段",
    )


def test_main_window_updates_overlay_and_reserve_button() -> None:
    _app()
    window = MainWindow(FakeFacade())

    window.apply_session_state(make_unauth_session())
    assert window.login_overlay.isVisible() is True
    assert window.action_bar.reserve_button.isEnabled() is False

    window.apply_session_state(make_authed_session())
    window.apply_board_state(make_board_state())
    window.apply_selection_state(make_selection())

    assert window.login_overlay.isVisible() is False
    assert window.action_bar.reserve_button.isEnabled() is True
    window.close()


def test_main_window_uses_panel_dialog_instead_of_persistent_dock() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert not hasattr(window, "detail_drawer")
    assert window.panel_dialog is not None
    window.close()


def test_toolbar_panel_button_opens_panel_dialog() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    window.top_toolbar.panel_button.click()

    assert window.panel_dialog.isVisible() is True
    window.close()


def test_main_window_defaults_to_compact_tool_size() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert window.width() <= 1040
    assert window.height() <= 760
    window.close()


def test_main_window_uses_home_first_widgets() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert window.top_toolbar is not None
    assert window.booking_card is not None
    assert window.action_bar is not None
    assert window.polling_summary is not None
    assert window.details_panel is not None
    window.close()


def test_main_window_exposes_primary_and_secondary_actions() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert window.action_bar.reserve_button.property("variant") == "primary"
    assert window.action_bar.query_button.property("variant") == "secondary"
    window.close()


def test_main_window_refresh_disables_actions_but_keeps_board() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())
    board = make_board_state()

    window.apply_session_state(make_authed_session())
    window.apply_board_state(board)
    window.apply_selection_state(make_selection())
    window.set_board_busy(True, "正在同步...")

    assert window.details_panel.board_table.rowCount() == 1
    assert window.action_bar.query_button.isEnabled() is False
    assert window.action_bar.reserve_button.isEnabled() is False
    assert "正在同步" in window.statusBar().currentMessage()
    window.close()


def test_main_window_stale_board_result_is_ignored() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    window.handle_board_loaded(2, make_board_state(date="2026-03-23"))
    window.handle_board_loaded(1, make_board_state(date="2026-03-22"))

    assert window.board_state is not None
    assert window.board_state.date == "2026-03-23"
    window.close()


def test_main_window_reserve_busy_freezes_selection() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())
    window.apply_session_state(make_authed_session())
    window.apply_board_state(make_board_state())
    window.apply_selection_state(make_selection())

    selected = window.selection_state
    window.set_reserve_busy(True, "正在预约...")
    window._handle_cell_clicked(0, 0)

    assert window.action_bar.reserve_button.isEnabled() is False
    assert window.selection_state == selected
    window.close()


def test_main_window_save_busy_disables_profile_switch() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    window.set_settings_busy(True, "正在保存...")

    assert window.top_toolbar.profile_combo.isEnabled() is False
    window.close()


def test_main_window_login_busy_disables_overlay_inputs() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())
    window.apply_session_state(make_unauth_session())

    window.set_session_busy("authenticating", True, "正在连接...")

    assert window.login_username.isEnabled() is False
    assert window.login_password.isEnabled() is False
    assert window.login_button.isEnabled() is False
    window.close()


def test_details_panel_is_collapsed_by_default() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())

    assert window.details_panel.is_expanded() is False
    window.close()


def test_polling_running_disables_query_and_reserve() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())
    window.apply_session_state(make_authed_session())
    window.apply_board_state(make_board_state())
    window.apply_selection_state(make_selection())

    window.apply_polling_state(make_running_polling_state())

    assert window.action_bar.query_button.isEnabled() is False
    assert window.action_bar.reserve_button.isEnabled() is False
    window.close()


def test_poll_start_rejection_does_not_start_local_coordinator() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=RejectingPollController())
    window.apply_session_state(make_authed_session())

    window.action_bar.poll_button.click()

    assert window.polling_state.status is PollingStatus.STOPPED
    assert window.action_bar.poll_button.text() == "开始轮询"
    window.close()


def test_board_busy_disables_poll_button_and_blocks_start() -> None:
    _app()
    window = MainWindow(FakeFacade(), controller=FakeController())
    window.apply_session_state(make_authed_session())
    window.set_board_busy(True, "正在同步...")

    assert window.action_bar.poll_button.isEnabled() is False
    window._toggle_polling()
    assert window.polling_state.status is PollingStatus.STOPPED
    window.close()
