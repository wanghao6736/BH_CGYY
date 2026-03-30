from __future__ import annotations

from typing import TYPE_CHECKING

from src.ui.facade import BoardQuery
from src.ui.polling import resolve_start_at
from src.ui.state import PollingStatus, SessionStatus
from src.ui.ui_mappers import (build_board_query, build_reserve_request,
                               build_selection_state)

if TYPE_CHECKING:
    from src.ui.window import MainWindow


class WindowActions:
    def __init__(self, window: MainWindow) -> None:
        self._window = window

    def open_panel_dialog(self) -> None:
        window = self._window
        window.panel_dialog.show()
        window.panel_dialog.raise_()
        window.panel_dialog.activateWindow()

    def toggle_board_panel(self) -> None:
        window = self._window
        if window.board_panel.isVisible():
            window.board_panel.hide()
        else:
            window.board_panel.show_at_bottom()

    def load_profiles(self, *, probe_session: bool = True) -> None:
        window = self._window
        profiles = window.facade.list_profiles()
        window.top_toolbar.set_profiles(
            [(item.display_name or item.name, item.name) for item in profiles]
        )
        if not profiles:
            return
        target_name = window.initial_profile_name or profiles[0].name
        index = next((i for i, item in enumerate(profiles) if item.name == target_name), 0)
        combo = window.top_toolbar.profile_combo
        was_blocked = combo.blockSignals(True)
        try:
            window.top_toolbar.set_current_profile_index(index)
        finally:
            combo.blockSignals(was_blocked)
        self.handle_profile_changed(profiles[index].name, probe_session=probe_session)

    def load_catalog(self, *, skip_auth_probe: bool = False) -> None:
        window = self._window
        profile_name = self.current_profile()
        if not profile_name:
            return
        window._latest_catalog_generation = window.controller.request_catalog_load(
            profile_name,
            skip_auth_probe=skip_auth_probe,
        )

    def current_profile(self) -> str:
        return self._window.top_toolbar.current_profile_data() or "default"

    def current_board_query(self, *, skip_auth_probe: bool = False) -> BoardQuery:
        window = self._window
        query = build_board_query(self.current_profile(), window.booking_card.collect_state())
        query.skip_auth_probe = skip_auth_probe
        return query

    def handle_profile_combo_changed(self, _index: int) -> None:
        self.handle_profile_changed(self.current_profile())

    def handle_profile_changed(self, profile_name: str, *, probe_session: bool = True) -> None:
        window = self._window
        if not profile_name or window._settings_busy:
            return
        window.polling_coordinator.stop()
        window.top_toolbar.set_sync_text("")
        window.apply_settings_state(window.facade.load_profile_form(profile_name))
        window.apply_selection_state(None)
        if not probe_session:
            return
        window._latest_session_generation = window.controller.request_session_probe(profile_name)
        window.set_session_busy(True, "检查连接...")

    def refresh_board(self, *, skip_auth_probe: bool = False) -> None:
        window = self._window
        query = self.current_board_query(skip_auth_probe=skip_auth_probe)
        window._latest_board_generation = window.controller.request_board_refresh(query)
        window.set_board_busy(True, "同步中...")

    def polling_tick(self, query: BoardQuery) -> None:
        window = self._window
        if window.session_state is None or window.session_state.status is not SessionStatus.AUTHENTICATED:
            return
        window._latest_board_generation = window.controller.request_board_refresh(query)

    def handle_heatmap_cell_clicked(self, row: int, col: int) -> None:
        window = self._window
        if window._reserve_busy or window._board_busy:
            return
        window.apply_selection_state(
            build_selection_state(
                window.board_state,
                row=row,
                col=col,
                current_selection=window.selection_state,
            )
        )

    def logout_current_profile(self) -> None:
        window = self._window
        window.polling_coordinator.stop()
        generation = window.controller.request_logout(self.current_profile())
        if generation is not None:
            window.apply_selection_state(None)
            window._latest_session_generation = generation
            window.set_session_busy(True, "退出中...")

    def save_settings(self) -> None:
        window = self._window
        state = window.panel_dialog.collect_state(profile_name=self.current_profile())
        generation = window.controller.request_save_settings(state)
        if generation is not None:
            window._latest_settings_generation = generation
            window.set_settings_busy(True, "保存中...")

    def toggle_polling(self) -> None:
        window = self._window
        running = window.polling_state.status in {
            PollingStatus.RUNNING,
            PollingStatus.STARTING,
            PollingStatus.STOPPING,
        }
        if running:
            window.polling_coordinator.stop()
            return

        window.poll_dialog.show_at_bottom()

    def start_polling_from_dialog(self) -> None:
        window = self._window
        config = window.poll_dialog.collect_config()
        window.poll_dialog.hide()
        if window._board_busy:
            return

        query = self.current_board_query(skip_auth_probe=True)
        start_at = resolve_start_at(config.start_time)
        window.polling_coordinator.start(query, interval_sec=config.interval_sec, start_at=start_at)

    def reserve_selected(self) -> None:
        window = self._window
        request = build_reserve_request(
            self.current_profile(),
            window.session_state.display_name if window.session_state is not None else "",
            window.booking_card.collect_state(),
            window.board_state,
            window.selection_state,
        )
        if request is None:
            return
        generation = window.controller.request_reserve(request)
        if generation is not None:
            window._latest_reserve_generation = generation
            window.set_reserve_busy(True, "预约中...")
