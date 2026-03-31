from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.notifier import build_payment_notification_message, describe_payment_target
from src.ui.state import (BoardState, BookingFormState, PollingState,
                          PollingStatus, ReserveOutcome, SelectionState,
                          SessionState, SessionStatus, SettingsFormState,
                          VenueCatalogItem, VenueCatalogState)
from src.ui.ui_mappers import (build_target_summary, matching_solutions,
                               resolve_reservable_solution)

if TYPE_CHECKING:
    from src.ui.window import MainWindow

logger = logging.getLogger(__name__)


class WindowPresenter:
    def __init__(self, window: MainWindow) -> None:
        self._window = window

    def _show_status_message(
        self,
        message: str,
        timeout_ms: int,
        *,
        level: int = logging.INFO,
    ) -> None:
        if not message:
            return
        logger.log(level, message)
        self._window.statusBar().showMessage(message, timeout_ms)

    def _sync_target_summary(self) -> None:
        window = self._window
        profile_name = window.top_toolbar.current_profile_data() or "default"
        summary = build_target_summary(
            window.booking_card.collect_state(),
            window.panel_dialog.collect_state(profile_name=profile_name),
            window.board_state,
            window.selection_state,
        )
        window.booking_card.set_target_summary(summary)
        window.panel_dialog.set_target_summary(summary)

    def apply_session_state(self, state: SessionState) -> None:
        window = self._window
        window.session_state = state
        window.top_toolbar.apply_session_state(state)
        self.sync_enabled_state()

    def apply_catalog_state(self, state: VenueCatalogState) -> None:
        window = self._window
        window.catalog_state = state
        window.booking_card.set_venue_data(state)

    def apply_polling_state(self, state: PollingState) -> None:
        window = self._window
        window.polling_state = state
        running = state.status in {
            PollingStatus.RUNNING,
            PollingStatus.STARTING,
            PollingStatus.STOPPING,
        }
        window.action_bar.set_polling_running(running)
        self.sync_enabled_state()

    def apply_board_state(self, state: BoardState) -> None:
        window = self._window
        if window.selection_state is not None and not matching_solutions(state, window.selection_state):
            window.selection_state = None
        window.board_state = state
        sync_text = f"{state.last_sync_at or '-'}"
        window.top_toolbar.set_sync_text(sync_text)
        window.booking_card.set_time_options(state.time_headers)
        if (
            window.catalog_state is None
            and state.campus_name
            and state.venue_name
            and state.site_name
        ):
            window.booking_card.set_venue_data(
                VenueCatalogState(
                    profile_name=state.profile_name,
                    items=[
                        VenueCatalogItem(
                            venue_site_id=state.venue_site_id,
                            site_name=state.site_name,
                            venue_name=state.venue_name,
                            campus_name=state.campus_name,
                        )
                    ],
                )
            )
        window.panel_dialog.set_time_options(state.time_headers)
        window.panel_dialog.set_buddy_options(
            state.available_buddies,
            buddy_num_min=state.buddy_num_min,
            buddy_num_max=state.buddy_num_max,
        )
        window.panel_dialog.apply_runtime_defaults(
            phone=state.runtime_phone,
            buddy_ids=[item.id for item in state.available_buddies],
        )
        window.board_panel.apply_board_state(state, window.selection_state)
        self._sync_target_summary()
        self.sync_enabled_state()

    def apply_selection_state(self, state: SelectionState | None) -> None:
        window = self._window
        window.selection_state = state
        self._sync_target_summary()
        if window.board_state is not None:
            window.board_panel.apply_board_state(window.board_state, state)
        self.sync_enabled_state()

    def apply_settings_state(self, state: SettingsFormState) -> None:
        window = self._window
        window.settings_state = state
        window.panel_dialog.apply_state(state)
        window.booking_card.apply_state(
            BookingFormState(
                date=state.default_search_date,
                start_time=state.start_time,
                slot_count=state.slot_count,
                venue_site_id=state.venue_site_id,
            )
        )
        self._sync_target_summary()

    def set_board_busy(self, busy: bool, message: str = "") -> None:
        window = self._window
        window._board_busy = busy
        self._show_status_message(message, 0 if busy else 3000)
        self.sync_enabled_state()

    def set_reserve_busy(self, busy: bool, message: str = "") -> None:
        window = self._window
        window._reserve_busy = busy
        self._show_status_message(message, 0 if busy else 3000)
        self.sync_enabled_state()

    def set_settings_busy(self, busy: bool, message: str = "") -> None:
        window = self._window
        window._settings_busy = busy
        self._show_status_message(message, 0 if busy else 3000)
        self.sync_enabled_state()

    def set_session_busy(self, busy: bool, message: str = "") -> None:
        window = self._window
        window._session_busy = busy
        self._show_status_message(message, 0 if busy else 3000)
        self.sync_enabled_state()

    def handle_lane_busy_changed(self, lane: str, busy: bool) -> None:
        if lane == "session":
            self.set_session_busy(busy, "连接中..." if busy else "")
        elif lane == "board":
            self.set_board_busy(busy, "同步中..." if busy else "")
        elif lane == "reserve":
            self.set_reserve_busy(busy, "预约中..." if busy else "")
        elif lane == "settings":
            self.set_settings_busy(busy, "保存中..." if busy else "")

    def handle_lane_failed(self, lane: str, generation: int, message: str) -> None:
        window = self._window
        if lane == "session" and generation != window._latest_session_generation:
            return
        if lane == "catalog" and generation != window._latest_catalog_generation:
            return
        if lane == "board" and generation != window._latest_board_generation:
            return
        if lane == "reserve" and generation != window._latest_reserve_generation:
            return
        if lane == "settings" and generation != window._latest_settings_generation:
            return
        if lane == "session":
            self.set_session_busy(False)
        elif lane == "catalog":
            self._show_status_message(message, 5000, level=logging.ERROR)
            return
        elif lane == "board":
            self.set_board_busy(False)
            if window.polling_state.status is PollingStatus.RUNNING:
                window.polling_coordinator.record_check(message=message)
        elif lane == "reserve":
            self.set_reserve_busy(False)
        elif lane == "settings":
            self.set_settings_busy(False)
        self._show_status_message(message, 5000, level=logging.ERROR)

    def handle_session_loaded(self, generation: int, state: SessionState) -> None:
        window = self._window
        if window._is_closing or generation < window._latest_session_generation:
            return
        window._latest_session_generation = generation
        self.set_session_busy(False)
        self.apply_session_state(state)
        if state.status is SessionStatus.AUTHENTICATED:
            window._load_catalog(skip_auth_probe=True)
            window._refresh_board(skip_auth_probe=True)
            return
        window.polling_coordinator.stop()
        window.apply_selection_state(None)
        window.loginRequired.emit(state.profile_name)

    def handle_catalog_loaded(self, generation: int, state: VenueCatalogState) -> None:
        window = self._window
        if window._is_closing or generation < window._latest_catalog_generation:
            return
        window._latest_catalog_generation = generation
        self.apply_catalog_state(state)

    def handle_board_loaded(self, generation: int, state: BoardState) -> None:
        window = self._window
        if window._is_closing or generation < window._latest_board_generation:
            return
        window._latest_board_generation = generation
        self.set_board_busy(False)
        self.apply_board_state(state)
        if window.polling_state.status is PollingStatus.RUNNING:
            window.polling_coordinator.record_check(
                checked_at=state.last_sync_at,
                message="检查完成",
            )
            if (
                window.session_state is not None
                and window.session_state.status is SessionStatus.AUTHENTICATED
                and not window._reserve_busy
                and resolve_reservable_solution(window.board_state, window.selection_state) is not None
            ):
                window.polling_coordinator.stop()
                self._show_status_message("轮询命中可预约方案，正在提交预约...", 5000)
                window._reserve_selected()
                return
        self._show_status_message("查询成功", 3000)

    def handle_reserve_finished(self, generation: int, result: ReserveOutcome) -> None:
        window = self._window
        if window._is_closing or generation != window._latest_reserve_generation:
            return
        self.set_reserve_busy(False)
        message = result.message or "预约完成"
        status_message = message
        if result.trade_no:
            status_message = f"{message} / {result.trade_no}"
        if result.payment_target:
            status_message = f"{status_message} / {describe_payment_target(result.payment_target)}已生成"
        elif result.payment_message:
            status_message = f"{status_message} / 支付待处理"
        self._show_status_message(status_message, 5000)
        if result.success:
            window.controller.request_notification(
                "CGYY 预约成功",
                build_payment_notification_message(
                    success=result.success,
                    message=message,
                    order_id=result.order_id,
                    trade_no=result.trade_no,
                    reservation_start_date=result.reservation_start_date,
                    reservation_end_date=result.reservation_end_date,
                    display_name=result.display_name,
                    profile_name=result.profile_name,
                    payment_target=result.payment_target,
                    payment_message=result.payment_message,
                ),
                url=result.payment_target,
                profile_name=result.profile_name or None,
            )

    def handle_settings_saved(self, generation: int, state: SettingsFormState) -> None:
        window = self._window
        if window._is_closing or generation != window._latest_settings_generation:
            return
        self.set_settings_busy(False)
        self.apply_settings_state(state)
        self._show_status_message("配置已保存", 3000)

    def sync_enabled_state(self) -> None:
        window = self._window
        authed = bool(window.session_state and window.session_state.status is SessionStatus.AUTHENTICATED)
        polling_active = window.polling_state.status in {
            PollingStatus.RUNNING,
            PollingStatus.STARTING,
            PollingStatus.STOPPING,
        }
        can_reserve = bool(
            authed
            and resolve_reservable_solution(window.board_state, window.selection_state) is not None
            and not window._board_busy
            and not window._reserve_busy
            and not window._session_busy
            and not polling_active
        )
        can_query = bool(
            authed
            and not window._board_busy
            and not window._reserve_busy
            and not window._session_busy
            and not polling_active
        )
        window.action_bar.set_reserve_enabled(can_reserve)
        window.action_bar.set_query_enabled(can_query)
        window.action_bar.set_poll_enabled(
            authed and not window._reserve_busy and not window._session_busy and not window._board_busy
        )
        window.top_toolbar.set_profiles_enabled(not window._settings_busy and not window._session_busy)
        window.top_toolbar.set_logout_enabled(
            authed and not window._session_busy and not window._reserve_busy
        )
        window.panel_dialog.set_save_enabled(not window._settings_busy)
