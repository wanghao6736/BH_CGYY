from __future__ import annotations

import logging
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QWidget

from src.parsers.slot_filter import SlotChoice, SlotSolution
from src.ui.form_options import build_date_options
from src.ui.state import (BoardCell, BoardRow, BoardState, BoardStatus,
                          BookingFormState, BuddyOption, LoginFormState,
                          PollingConfigState, ProfileOption, SelectionState,
                          PollingStatus, ReserveOutcome, SessionState,
                          SessionStatus, SettingsFormState, VenueCatalogItem,
                          VenueCatalogState)
from src.ui.widgets.board_panel import BoardPanel
from src.ui.widgets.booking_card import BookingCard
from src.ui.widgets.login_panel import LoginWindow
from src.ui.widgets.activity_panel import ActivityPanel
from src.ui.widgets.panel_dialog import PanelDialog
from src.ui.widgets.poll_dialog import PollDialog
from src.ui.window import MainWindow


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class DummySignal:
    def connect(self, callback) -> None:  # pragma: no cover - trivial stub
        self.callback = callback


class FakeController:
    def __init__(self) -> None:
        self.session_loaded = DummySignal()
        self.catalog_loaded = DummySignal()
        self.board_loaded = DummySignal()
        self.reserve_finished = DummySignal()
        self.settings_loaded = DummySignal()
        self.lane_busy_changed = DummySignal()
        self.lane_failed = DummySignal()
        self.notification_requests = []

    def request_session_probe(self, profile_name: str) -> int:
        return 1

    def request_catalog_load(self, profile_name: str, *, skip_auth_probe: bool = False) -> int:
        return 2

    def request_board_refresh(self, query) -> int:
        return 3

    def request_reserve(self, request) -> int:
        return 6

    def request_login(
        self,
        profile_name: str,
        username: str,
        password: str,
        *,
        persist_auth: bool = True,
    ) -> int:
        return 4

    def request_logout(self, profile_name: str) -> int:
        return 5

    def request_notification(
        self,
        title: str,
        message: str,
        *,
        profile_name: str | None = None,
    ) -> None:
        self.notification_requests.append((title, message, profile_name))


def _choice(space_id: int, time_id: int, space_name: str, start: str, end: str, fee: float = 25.0) -> SlotChoice:
    return SlotChoice(
        space_id=space_id,
        time_id=time_id,
        space_name=space_name,
        start_time=start,
        end_time=end,
        order_fee=fee,
    )


def _solution(*choices: SlotChoice) -> SlotSolution:
    return SlotSolution(
        choices=list(choices),
        total_fee=sum(item.order_fee for item in choices),
        slot_count=len(choices),
        total_hours=0.5 * len(choices),
    )


def _board_state(
    *,
    solutions: list[SlotSolution] | None = None,
    last_sync_at: str = "10:20:30",
) -> BoardState:
    return BoardState(
        status=BoardStatus.READY,
        profile_name="default",
        venue_site_id=57,
        venue_label="Test Venue",
        date=QDate.currentDate().toString("yyyy-MM-dd"),
        slot_count=2,
        available_dates=[QDate.currentDate().toString("yyyy-MM-dd")],
        rows=[],
        solutions=list(solutions or []),
        time_headers=["18:00", "18:30"],
        last_sync_at=last_sync_at,
    )


def test_booking_card_apply_and_collect_state_roundtrip() -> None:
    _app()
    target_date = QDate.currentDate().addDays(2).toString("yyyy-MM-dd")
    card = BookingCard()

    card.apply_state(
        BookingFormState(
            date=target_date,
            start_time="18:30",
            slot_count=3,
            venue_site_id=57,
        )
    )

    state = card.collect_state()

    assert state.date == target_date
    assert state.start_time == "18:30"
    assert state.slot_count == 3
    assert state.venue_site_id == 57


def test_booking_card_combo_buttons_fill_fixed_width_after_show() -> None:
    app = _app()
    card = BookingCard()
    card.show()
    app.processEvents()

    for combo in (
        card.date_combo,
        card.time_combo,
        card.slot_combo,
        card.campus_combo,
        card.venue_combo,
        card.court_combo,
    ):
        assert combo._button.width() == combo.width()

    card.close()


def test_booking_card_collect_state_normalizes_any_time_option() -> None:
    _app()
    card = BookingCard()
    card.time_combo.setCurrentIndex(0)

    assert card.collect_state().start_time == ""


def test_booking_card_preserves_applied_site_before_catalog_injection() -> None:
    _app()
    card = BookingCard()
    target_date = QDate.currentDate().addDays(2).toString("yyyy-MM-dd")

    card.apply_state(
        BookingFormState(
            date=target_date,
            start_time="18:30",
            slot_count=2,
            venue_site_id=999,
        )
    )

    assert card.collect_state().venue_site_id == 999


def test_booking_card_selects_matching_site_after_catalog_injection() -> None:
    _app()
    card = BookingCard()
    card.apply_state(
        BookingFormState(
            date=QDate.currentDate().toString("yyyy-MM-dd"),
            start_time="18:00",
            slot_count=2,
            venue_site_id=58,
        )
    )
    card.set_venue_data(
        VenueCatalogState(
            profile_name="default",
            items=[
                VenueCatalogItem(
                    venue_site_id=57,
                    site_name="羽毛球",
                    venue_name="2号馆",
                    campus_name="学院路",
                ),
                VenueCatalogItem(
                    venue_site_id=58,
                    site_name="乒乓球",
                    venue_name="3号馆",
                    campus_name="学院路",
                ),
            ],
        )
    )

    state = card.collect_state()
    assert state.venue_site_id == 58
    assert card.court_combo.currentText() == "乒乓球"


def test_panel_dialog_apply_and_collect_state_roundtrip() -> None:
    _app()
    target_date = QDate.currentDate().addDays(3).toString("yyyy-MM-dd")
    dialog = PanelDialog()

    dialog.apply_state(
        SettingsFormState(
            profile_name="default",
            display_name="Tester",
            phone="123456",
            buddy_ids="1,2",
            selection_strategy="same_first_digit,cheapest",
            venue_site_id=57,
            default_search_date=target_date,
            start_time="19:00",
            slot_count=4,
        )
    )

    state = dialog.collect_state()

    assert state.profile_name == "default"
    assert state.display_name == "Tester"
    assert state.phone == "123456"
    assert state.buddy_ids == "1,2"
    assert state.selection_strategy == "same_first_digit,cheapest"
    assert state.venue_site_id == 57
    assert state.default_search_date == target_date
    assert state.start_time == "19:00"
    assert state.slot_count == 4


def test_panel_dialog_collect_state_normalizes_any_time_option() -> None:
    _app()
    dialog = PanelDialog()
    dialog.settings_start_input.setCurrentIndex(0)

    assert dialog.collect_state().start_time == ""


def test_panel_dialog_runtime_defaults_only_fill_empty_fields() -> None:
    _app()
    dialog = PanelDialog()
    dialog.phone_input.setText("")
    dialog.set_buddy_options(
        [BuddyOption(id="1", name="Alice"), BuddyOption(id="2", name="Bob")],
        buddy_num_min=1,
    )

    dialog.apply_runtime_defaults(phone="13900000000", buddy_ids=["1", "2"])
    assert dialog.phone_input.text() == "13900000000"
    assert dialog.collect_state().buddy_ids == "1,2"

    dialog.phone_input.setText("13800000000")
    dialog.apply_state(
        SettingsFormState(
            profile_name="default",
            phone="13800000000",
            buddy_ids="9",
        )
    )
    dialog.apply_runtime_defaults(phone="13900000001", buddy_ids=["2"])
    assert dialog.phone_input.text() == "13800000000"
    assert dialog.collect_state().buddy_ids == "9"


def test_panel_dialog_maps_buddy_ids_to_names_in_dropdown() -> None:
    _app()
    dialog = PanelDialog()
    dialog.apply_state(SettingsFormState(profile_name="default", buddy_ids="2"))
    dialog.set_buddy_options(
        [BuddyOption(id="1", name="Alice"), BuddyOption(id="2", name="Bob")],
        buddy_num_min=1,
    )

    assert dialog.buddy_combo.currentText() == "Bob"
    assert dialog.collect_state().buddy_ids == "2"


def test_panel_dialog_shows_joined_labels_for_multi_select_fields() -> None:
    _app()
    dialog = PanelDialog()
    dialog.apply_state(
        SettingsFormState(
            profile_name="default",
            buddy_ids="1,2",
            selection_strategy="same_first_digit,same_venue,cheapest",
        )
    )
    dialog.set_buddy_options(
        [BuddyOption(id="1", name="Alice"), BuddyOption(id="2", name="Bob")],
        buddy_num_min=1,
    )

    assert "Alice, Bob" in dialog.buddy_combo.currentText()
    assert dialog.buddy_combo._button.toolTip() == "Alice, Bob"
    assert dialog.strategy_combo.currentText() == "同一场馆, 同一场地, 最低价格"
    assert dialog.strategy_combo._button.toolTip() == "同一场馆, 同一场地, 最低价格"
    assert dialog.collect_state().buddy_ids == "1,2"
    assert dialog.collect_state().selection_strategy == "same_first_digit,same_venue,cheapest"


def test_panel_dialog_emits_save_requested() -> None:
    _app()
    dialog = PanelDialog()
    triggered: list[bool] = []
    dialog.saveRequested.connect(lambda: triggered.append(True))

    dialog.save_settings_button.click()

    assert triggered == [True]


def test_poll_dialog_apply_and_collect_config_roundtrip() -> None:
    _app()
    dialog = PollDialog()
    start_time = dialog.start_time_combo.currentText()

    dialog.apply_config(PollingConfigState(start_time=start_time, interval_sec=300))

    state = dialog.collect_config()

    assert state.start_time == start_time
    assert state.interval_sec == 300


def test_board_panel_renders_selection_from_board_state() -> None:
    _app()
    panel = BoardPanel()
    board_state = BoardState(
        status=BoardStatus.READY,
        profile_name="default",
        venue_site_id=57,
        venue_label="Test Venue",
        date=QDate.currentDate().toString("yyyy-MM-dd"),
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
                        reservation_status=1,
                        selectable=True,
                    ),
                    BoardCell(
                        space_id=101,
                        space_name="A1",
                        time_id=2,
                        begin_time="18:30",
                        end_time="19:00",
                        label="18:30",
                        reservation_status=1,
                        selectable=True,
                    ),
                ],
            )
        ],
        solutions=[
            _solution(
                _choice(101, 1, "A1", "18:00", "18:30"),
                _choice(101, 2, "A1", "18:30", "19:00"),
            )
        ],
        time_headers=["18:00", "18:30"],
        last_sync_at="10:20:30",
    )
    selection = SelectionState(
        choices=[
            _choice(101, 1, "A1", "18:00", "18:30"),
            _choice(101, 2, "A1", "18:30", "19:00"),
        ]
    )

    panel.apply_board_state(board_state, selection)

    first_cell = panel.heatmap.get_cell(0, 0)
    second_cell = panel.heatmap.get_cell(0, 1)
    assert first_cell is not None and first_cell.selected is True
    assert second_cell is not None and second_cell.selected is True
    assert panel.selection_summary.text() == "A1 18:00-18:30 / A1 18:30-19:00"
    assert panel.sync_label.text() == "10:20:30"


def test_board_panel_shows_recommended_solution_summary_without_manual_selection() -> None:
    _app()
    panel = BoardPanel()
    board_state = _board_state(
        solutions=[
            _solution(
                _choice(101, 1, "A1", "18:00", "18:30"),
                _choice(101, 2, "A1", "18:30", "19:00"),
            )
        ]
    )

    panel.apply_board_state(board_state, None)

    assert "推荐方案:" in panel.selection_summary.text()
    assert "A1 18:00-18:30 / A1 18:30-19:00" in panel.selection_summary.text()


def test_board_panel_keeps_available_status_for_range_blocked_cell() -> None:
    _app()
    panel = BoardPanel()
    board_state = BoardState(
        status=BoardStatus.READY,
        profile_name="default",
        venue_site_id=57,
        venue_label="Test Venue",
        date=QDate.currentDate().toString("yyyy-MM-dd"),
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
                        reservation_status=1,
                        selectable=False,
                    ),
                    BoardCell(
                        space_id=101,
                        space_name="A1",
                        time_id=2,
                        begin_time="18:30",
                        end_time="19:00",
                        label="18:30",
                        reservation_status=4,
                        selectable=False,
                    ),
                ],
            )
        ],
        solutions=[],
        time_headers=["18:00", "18:30"],
    )

    panel.apply_board_state(board_state)

    first_cell = panel.heatmap.get_cell(0, 0)
    second_cell = panel.heatmap.get_cell(0, 1)
    assert first_cell is not None
    assert first_cell.status.name == "AVAILABLE"
    assert first_cell.enabled is False
    assert first_cell.range_blocked is True
    assert second_cell is not None
    assert second_cell.status.name == "RESERVED"
    assert second_cell.range_blocked is False


def test_board_panel_is_positioned_below_parent_window() -> None:
    app = _app()
    parent = QWidget()
    parent.setGeometry(140, 120, 420, 300)
    parent.show()
    app.processEvents()

    panel = BoardPanel(parent)
    panel.show_at_bottom()
    app.processEvents()
    app.processEvents()

    parent_rect = parent.frameGeometry()
    assert panel.frameGeometry().top() >= parent_rect.bottom()

    panel.hide()
    parent.close()


def test_activity_panel_is_hidden_until_message_is_appended() -> None:
    _app()
    panel = ActivityPanel()
    logger = logging.getLogger("tests.activity_panel")
    handler = panel.create_log_handler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    assert panel.isHidden() is True

    logger.info("hello activity")

    assert panel.isHidden() is False
    assert "hello activity" in panel.output.toPlainText()

    logger.removeHandler(handler)
    handler.close()


def test_main_window_poll_dialog_interval_flows_to_local_coordinator() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    window = MainWindow(FakeFacade(), controller=FakeController())
    captured: list[int | None] = []
    original_start = window.polling_coordinator.start

    def capture_start(query, *, interval_sec=None, start_at=None):
        captured.append((interval_sec, start_at, query.skip_auth_probe))
        return True

    window.polling_coordinator.start = capture_start  # type: ignore[method-assign]
    current_start = window.poll_dialog.start_time_combo.currentText()
    window.poll_dialog.apply_config(PollingConfigState(start_time=current_start, interval_sec=600))
    window._start_polling_from_dialog()

    window.polling_coordinator.start = original_start  # type: ignore[method-assign]
    window.close()

    assert captured and captured[0][0] == 600
    assert captured[0][1] is not None
    assert captured[0][2] is True


def test_main_window_board_load_updates_polling_state_via_coordinator() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    window = MainWindow(FakeFacade(), controller=FakeController())
    window.polling_coordinator.start(window._actions.current_board_query(), interval_sec=60)

    board_state = BoardState(
        status=BoardStatus.READY,
        profile_name="default",
        venue_site_id=57,
        venue_label="Test Venue",
        date=QDate.currentDate().toString("yyyy-MM-dd"),
        slot_count=2,
        available_dates=[QDate.currentDate().toString("yyyy-MM-dd")],
        rows=[],
        solutions=[
            _solution(
                _choice(101, 1, "A1", "18:00", "18:30"),
                _choice(101, 2, "A1", "18:30", "19:00"),
            )
        ],
        time_headers=["18:00", "18:30"],
        runtime_phone="13900000000",
        available_buddies=[BuddyOption(id="1", name="Alice"), BuddyOption(id="2", name="Bob")],
        buddy_num_min=1,
        campus_name="沙河校区",
        venue_name="综合馆",
        site_name="羽毛球馆",
        last_sync_at="10:20:30",
    )
    window.handle_board_loaded(1, board_state)

    assert window.polling_coordinator.state.last_checked_at == "10:20:30"
    assert window.polling_coordinator.state.last_message == "检查完成"
    assert window.polling_state.last_checked_at == "10:20:30"
    assert window.polling_state.last_message == "检查完成"
    assert window.panel_dialog.phone_input.text() == "13900000000"
    assert window.panel_dialog.collect_state().buddy_ids == "1,2"
    assert window.booking_card.date_combo.count() == 7
    assert window.booking_card.date_combo.itemText(0) == build_date_options()[0]
    assert window.panel_dialog.settings_date_input.count() == 7
    assert window.panel_dialog.settings_date_input.itemText(0) == build_date_options()[0]
    assert window.booking_card.time_combo.currentText() == "-"
    assert "场地ID-57 buddy ID 1,2" in window.booking_card.target_summary.text()
    assert "沙河校区 综合馆 羽毛球馆 A1 18:00-18:30 / A1 18:30-19:00" in window.booking_card.target_summary.text()
    window.close()


def test_main_window_activity_panel_receives_status_messages() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    window = MainWindow(FakeFacade(), controller=FakeController())

    assert "检查连接..." in window.activity_panel.output.toPlainText()

    window.set_board_busy(True, "同步中...")

    assert window.activity_panel.isHidden() is False
    assert "同步中..." in window.activity_panel.output.toPlainText()
    window.close()


def test_main_window_enables_reserve_button_when_board_load_has_recommended_solution() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    window = MainWindow(FakeFacade(), controller=FakeController())
    window.set_session_busy(False)
    window.apply_session_state(
        SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.AUTHENTICATED,
        )
    )

    window.handle_board_loaded(
        1,
        _board_state(
            solutions=[
                _solution(
                    _choice(101, 1, "A1", "18:00", "18:30"),
                    _choice(101, 2, "A1", "18:30", "19:00"),
                )
            ]
        ),
    )

    assert window.action_bar.reserve_button.isEnabled() is True
    window.close()


def test_main_window_disables_reserve_button_when_new_board_has_no_reservable_solution() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    window = MainWindow(FakeFacade(), controller=FakeController())
    window.set_session_busy(False)
    window.apply_session_state(
        SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.AUTHENTICATED,
        )
    )
    window.handle_board_loaded(
        1,
        _board_state(
            solutions=[
                _solution(
                    _choice(101, 1, "A1", "18:00", "18:30"),
                    _choice(101, 2, "A1", "18:30", "19:00"),
                )
            ],
            last_sync_at="10:20:30",
        ),
    )
    window.apply_selection_state(
        SelectionState(
            choices=[
                _choice(101, 1, "A1", "18:00", "18:30"),
                _choice(101, 2, "A1", "18:30", "19:00"),
            ]
        )
    )

    window.handle_board_loaded(2, _board_state(solutions=[], last_sync_at="10:21:00"))

    assert window.selection_state is None
    assert window.action_bar.reserve_button.isEnabled() is False
    window.close()


def test_main_window_auto_reserves_when_polling_finds_recommended_solution() -> None:
    _app()

    class RecordingController(FakeController):
        def __init__(self) -> None:
            super().__init__()
            self.reserve_requests = []

        def request_reserve(self, request) -> int:
            self.reserve_requests.append(request)
            return 7

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    controller = RecordingController()
    window = MainWindow(FakeFacade(), controller=controller)
    window.set_session_busy(False)
    window.apply_session_state(
        SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.AUTHENTICATED,
        )
    )
    window.polling_coordinator.start(window._actions.current_board_query(skip_auth_probe=True), interval_sec=60)

    window.handle_board_loaded(
        1,
        _board_state(
            solutions=[
                _solution(
                    _choice(101, 1, "A1", "18:00", "18:30"),
                    _choice(101, 2, "A1", "18:30", "19:00"),
                )
            ]
        ),
    )

    assert len(controller.reserve_requests) == 1
    assert window.polling_coordinator.state.status is PollingStatus.STOPPED
    assert window._latest_reserve_generation == 7
    window.close()


def test_main_window_reserve_success_sends_notification_uses_result_context() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    controller = FakeController()
    window = MainWindow(FakeFacade(), controller=controller)
    window.apply_session_state(
        SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.AUTHENTICATED,
        )
    )
    window._latest_reserve_generation = 7
    window.apply_session_state(
        SessionState(
            profile_name="secondary",
            display_name="次要用户",
            status=SessionStatus.AUTHENTICATED,
        )
    )

    window.handle_reserve_finished(
        7,
        ReserveOutcome(
            success=True,
            message="OK",
            trade_no="D123",
            order_id=456,
            reservation_start_date="2026-04-01 18:00",
            reservation_end_date="2026-04-01 19:00",
            profile_name="default",
            display_name="默认用户",
        ),
    )

    assert controller.notification_requests == [
        (
            "CGYY 预约成功",
            "✅ [成功] 提交订单：OK\n"
            "   📌 订单ID 456 | 编号 D123\n"
            "   🕐 预约时间 2026-04-01 18:00 ~ 2026-04-01 19:00\n"
            "   👤 预定人 默认用户 | profile default",
            "default",
        )
    ]
    window.close()


def test_authenticated_session_triggers_catalog_and_board_loads() -> None:
    _app()

    class RecordingController(FakeController):
        def __init__(self) -> None:
            super().__init__()
            self.catalog_requests: list[str] = []
            self.board_requests: list[object] = []

        def request_catalog_load(self, profile_name: str, *, skip_auth_probe: bool = False) -> int:
            self.catalog_requests.append((profile_name, skip_auth_probe))
            return 2

        def request_board_refresh(self, query) -> int:
            self.board_requests.append(query)
            return 3

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name, venue_site_id=57)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    controller = RecordingController()
    window = MainWindow(FakeFacade(), controller=controller)
    window.handle_session_loaded(
        1,
        SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.AUTHENTICATED,
        ),
    )

    assert controller.catalog_requests == [("default", True)]
    assert len(controller.board_requests) == 1
    assert controller.board_requests[0].profile_name == "default"
    assert controller.board_requests[0].skip_auth_probe is True
    window.close()


def test_main_window_uses_initial_session_state_without_extra_probe() -> None:
    _app()

    class RecordingController(FakeController):
        def __init__(self) -> None:
            super().__init__()
            self.session_requests: list[str] = []
            self.catalog_requests: list[tuple[str, bool]] = []
            self.board_requests: list[object] = []

        def request_session_probe(self, profile_name: str) -> int:
            self.session_requests.append(profile_name)
            return 1

        def request_catalog_load(self, profile_name: str, *, skip_auth_probe: bool = False) -> int:
            self.catalog_requests.append((profile_name, skip_auth_probe))
            return 2

        def request_board_refresh(self, query) -> int:
            self.board_requests.append(query)
            return 3

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name, venue_site_id=57)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    controller = RecordingController()
    window = MainWindow(
        FakeFacade(),
        controller=controller,
        initial_profile_name="default",
        initial_session_state=SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.AUTHENTICATED,
        ),
        show_on_init=False,
    )

    assert controller.session_requests == []
    assert controller.catalog_requests == [("default", True)]
    assert len(controller.board_requests) == 1
    assert controller.board_requests[0].skip_auth_probe is True
    window.close()


def test_main_window_initial_profile_selection_does_not_double_probe() -> None:
    _app()

    class RecordingController(FakeController):
        def __init__(self) -> None:
            super().__init__()
            self.session_requests: list[str] = []

        def request_session_probe(self, profile_name: str) -> int:
            self.session_requests.append(profile_name)
            return len(self.session_requests)

    class FakeFacade:
        def list_profiles(self):
            return [
                ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self"),
                ProfileOption(name="secondary", display_name="次要用户", auth_source="self", sso_source="self"),
            ]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name, venue_site_id=57)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    controller = RecordingController()
    window = MainWindow(
        FakeFacade(),
        controller=controller,
        initial_profile_name="secondary",
        show_on_init=False,
    )

    assert controller.session_requests == ["secondary"]
    window.close()


def test_unauthenticated_session_redirects_home_back_to_login() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name, venue_site_id=57)

    window = MainWindow(FakeFacade(), controller=FakeController())
    redirected: list[str] = []
    window.loginRequired.connect(redirected.append)
    window.handle_session_loaded(
        1,
        SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.UNAUTHENTICATED,
        ),
    )

    assert redirected == ["default"]
    window.close()


def test_logout_button_requests_logout_for_current_profile() -> None:
    _app()

    class RecordingController(FakeController):
        def __init__(self) -> None:
            super().__init__()
            self.logout_requests: list[str] = []

        def request_logout(self, profile_name: str) -> int:
            self.logout_requests.append(profile_name)
            return 4

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_profile_form(self, profile_name: str) -> SettingsFormState:
            return SettingsFormState(profile_name=profile_name)

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(profile_name=profile_name)

    controller = RecordingController()
    window = MainWindow(FakeFacade(), controller=controller)
    window.set_session_busy(False)
    window.apply_session_state(
        SessionState(
            profile_name="default",
            display_name="默认用户",
            status=SessionStatus.AUTHENTICATED,
        )
    )

    window.top_toolbar.logout_button.click()

    assert controller.logout_requests == ["default"]
    window.close()


def test_login_window_defaults_to_persist_auth() -> None:
    _app()

    class FakeFacade:
        def list_profiles(self):
            return [ProfileOption(name="default", display_name="默认用户", auth_source="self", sso_source="self")]

        def load_login_form(self, profile_name: str) -> LoginFormState:
            return LoginFormState(
                profile_name=profile_name,
                username="",
                persist_auth=True,
            )

    window = LoginWindow(FakeFacade(), controller=FakeController())

    assert window.username_input.text() == ""
    assert window.persist_auth_checkbox.isChecked() is True
    assert window.password_input.text() == ""
    assert window._persist_mode_text == "登录后保持登录"
    window.close()


def test_poll_dialog_preserves_selected_interval_when_reopened() -> None:
    app = _app()
    parent = QWidget()
    parent.setGeometry(120, 140, 420, 300)
    parent.show()
    app.processEvents()

    dialog = PollDialog(parent)
    current_start = dialog.start_time_combo.currentText()
    dialog.apply_config(PollingConfigState(start_time=current_start, interval_sec=600))
    dialog.show_at_bottom()
    app.processEvents()

    assert dialog.collect_config().interval_sec == 600

    dialog.hide()
    parent.close()
