from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QStatusBar, QVBoxLayout, QWidget

from src.logging_setup import setup_logging
from src.ui.facade import BoardQuery
from src.ui.polling import PollingCoordinator
from src.ui.state import (BoardState, PollingState, SelectionState,
                          SessionState, SessionStatus, SettingsFormState,
                          VenueCatalogState)
from src.ui.styles import load_stylesheet
from src.ui.widgets import (ActivityPanel, ActionBar, BookingCard, PanelDialog, PollDialog,
                            TopToolbar)
from src.ui.widgets.board_panel import BoardPanel
from src.ui.window_actions import WindowActions
from src.ui.window_presenter import WindowPresenter


class MainWindow(QMainWindow):
    loginRequired = Signal(str)

    def __init__(
        self,
        facade,
        *,
        controller,
        initial_profile_name: str | None = None,
        initial_session_state: SessionState | None = None,
        show_on_init: bool = True,
    ) -> None:
        super().__init__()
        setup_logging()
        self.facade = facade
        self.controller = controller
        self.initial_profile_name = initial_profile_name
        self.initial_session_state = initial_session_state
        self.session_state: SessionState | None = None
        self.catalog_state: VenueCatalogState | None = None
        self.board_state: BoardState | None = None
        self.selection_state: SelectionState | None = None
        self.settings_state: SettingsFormState | None = None
        self.polling_state = PollingState()
        self._board_busy = False
        self._reserve_busy = False
        self._settings_busy = False
        self._session_busy = False
        self._latest_session_generation = 0
        self._latest_catalog_generation = 0
        self._latest_board_generation = 0
        self._latest_reserve_generation = 0
        self._latest_settings_generation = 0
        self._is_closing = False

        self._presenter = WindowPresenter(self)
        self._actions = WindowActions(self)
        self.polling_coordinator = PollingCoordinator(on_tick=self._polling_tick)
        self.polling_coordinator.state_changed.connect(self.apply_polling_state)

        self._build_ui()
        self._bind_controller()
        self._load_profiles(probe_session=initial_session_state is None)
        if initial_session_state is not None:
            self.apply_session_state(initial_session_state)
            if initial_session_state.status is SessionStatus.AUTHENTICATED:
                self._actions.load_catalog(skip_auth_probe=True)
                self._actions.refresh_board(skip_auth_probe=True)
        self.setWindowTitle("BUAA CGYY")
        self.resize(360, 240)
        if show_on_init:
            self.show()

    def _bind_controller(self) -> None:
        self.controller.session_loaded.connect(self.handle_session_loaded)
        self.controller.catalog_loaded.connect(self.handle_catalog_loaded)
        self.controller.board_loaded.connect(self.handle_board_loaded)
        self.controller.reserve_finished.connect(self.handle_reserve_finished)
        self.controller.settings_loaded.connect(self.handle_settings_saved)
        self.controller.lane_busy_changed.connect(self._handle_lane_busy_changed)
        self.controller.lane_failed.connect(self._handle_lane_failed)

    def _build_ui(self) -> None:
        self.setStatusBar(QStatusBar(self))
        self.setStyleSheet(load_stylesheet())

        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        self.top_toolbar = TopToolbar()
        root_layout.addWidget(self.top_toolbar)

        self.booking_card = BookingCard()
        root_layout.addWidget(self.booking_card)

        self.action_bar = ActionBar()
        root_layout.addWidget(self.action_bar)

        self.activity_panel = ActivityPanel()
        self._activity_log_handler = self.activity_panel.create_log_handler()
        logging.getLogger().addHandler(self._activity_log_handler)
        root_layout.addWidget(self.activity_panel)

        self.board_panel = BoardPanel(self)
        self.board_panel.cellClicked.connect(self._handle_heatmap_cell_clicked)

        self.panel_dialog = PanelDialog(self)
        self.poll_dialog = PollDialog(self)

        self.action_bar.reserveRequested.connect(self._reserve_selected)
        self.action_bar.queryRequested.connect(self._refresh_board)
        self.action_bar.pollRequested.connect(self._toggle_polling)
        self.action_bar.detailsRequested.connect(self._toggle_board_panel)
        self.top_toolbar.profileChanged.connect(self._handle_profile_combo_changed)
        self.top_toolbar.logoutRequested.connect(self._logout_current_profile)
        self.top_toolbar.settingsRequested.connect(self._open_panel_dialog)
        self.panel_dialog.saveRequested.connect(self._save_settings)
        self.poll_dialog.startRequested.connect(self._start_polling_from_dialog)

    def _open_panel_dialog(self) -> None:
        self._actions.open_panel_dialog()

    def _toggle_board_panel(self) -> None:
        self._actions.toggle_board_panel()

    def _load_profiles(self, *, probe_session: bool = True) -> None:
        self._actions.load_profiles(probe_session=probe_session)

    def _load_catalog(self, *, skip_auth_probe: bool = False) -> None:
        self._actions.load_catalog(skip_auth_probe=skip_auth_probe)

    def _handle_profile_combo_changed(self, _index: int) -> None:
        self._actions.handle_profile_combo_changed(_index)

    def apply_session_state(self, state: SessionState) -> None:
        self._presenter.apply_session_state(state)

    def apply_catalog_state(self, state: VenueCatalogState) -> None:
        self._presenter.apply_catalog_state(state)

    def apply_polling_state(self, state: PollingState) -> None:
        self._presenter.apply_polling_state(state)

    def apply_board_state(self, state: BoardState) -> None:
        self._presenter.apply_board_state(state)

    def apply_selection_state(self, state: SelectionState | None) -> None:
        self._presenter.apply_selection_state(state)

    def apply_settings_state(self, state: SettingsFormState) -> None:
        self._presenter.apply_settings_state(state)

    def _refresh_board(self, *, skip_auth_probe: bool = False) -> None:
        self._actions.refresh_board(skip_auth_probe=skip_auth_probe)

    def _polling_tick(self, query: BoardQuery) -> None:
        self._actions.polling_tick(query)

    def _handle_heatmap_cell_clicked(self, row: int, col: int) -> None:
        self._actions.handle_heatmap_cell_clicked(row, col)

    def _logout_current_profile(self) -> None:
        self._actions.logout_current_profile()

    def _save_settings(self) -> None:
        self._actions.save_settings()

    def _toggle_polling(self) -> None:
        self._actions.toggle_polling()

    def _start_polling_from_dialog(self) -> None:
        self._actions.start_polling_from_dialog()

    def _reserve_selected(self) -> None:
        self._actions.reserve_selected()

    def set_board_busy(self, busy: bool, message: str = "") -> None:
        self._presenter.set_board_busy(busy, message)

    def set_reserve_busy(self, busy: bool, message: str = "") -> None:
        self._presenter.set_reserve_busy(busy, message)

    def set_settings_busy(self, busy: bool, message: str = "") -> None:
        self._presenter.set_settings_busy(busy, message)

    def set_session_busy(self, busy: bool, message: str = "") -> None:
        self._presenter.set_session_busy(busy, message)

    def _handle_lane_busy_changed(self, lane: str, busy: bool) -> None:
        self._presenter.handle_lane_busy_changed(lane, busy)

    def _handle_lane_failed(self, lane: str, generation: int, message: str) -> None:
        self._presenter.handle_lane_failed(lane, generation, message)

    def handle_session_loaded(self, generation: int, state: SessionState) -> None:
        self._presenter.handle_session_loaded(generation, state)

    def handle_catalog_loaded(self, generation: int, state: VenueCatalogState) -> None:
        self._presenter.handle_catalog_loaded(generation, state)

    def handle_board_loaded(self, generation: int, state: BoardState) -> None:
        self._presenter.handle_board_loaded(generation, state)

    def handle_reserve_finished(self, generation: int, result) -> None:
        self._presenter.handle_reserve_finished(generation, result)

    def handle_settings_saved(self, generation: int, state: SettingsFormState) -> None:
        self._presenter.handle_settings_saved(generation, state)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._is_closing = True
        logging.getLogger().removeHandler(self._activity_log_handler)
        self._activity_log_handler.close()
        self.polling_coordinator.stop()
        if self.poll_dialog.isVisible():
            self.poll_dialog.hide()
        if self.panel_dialog.isVisible():
            self.panel_dialog.close()
        if self.board_panel.isVisible():
            self.board_panel.close()
        super().closeEvent(event)
