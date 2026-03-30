from __future__ import annotations

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QPushButton, QStatusBar,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from src.ui.animations import build_expand_animation
from src.ui.facade import BoardQuery, ReserveRequest
from src.ui.polling import PollingCoordinator
from src.ui.state import (BoardCell, BoardState, PollingState, PollingStatus,
                          ReserveOutcome, SelectionState, SessionState,
                          SessionStatus, SettingsFormState)
from src.ui.theme import APP_QSS
from src.ui.widgets import (ActionBar, BoardDialog, BookingCard, PanelDialog,
                            PollDialog, PollingSummary, TopToolbar)


class MainWindow(QMainWindow):
    def __init__(self, facade, *, controller=None) -> None:
        super().__init__()
        self.facade = facade
        self.controller = controller
        self.session_state: SessionState | None = None
        self.board_state: BoardState | None = None
        self.selection_state: SelectionState | None = None
        self.settings_state: SettingsFormState | None = None
        self.polling_state = PollingState()
        self._cell_lookup: dict[tuple[int, int], BoardCell] = {}
        self._board_busy = False
        self._reserve_busy = False
        self._settings_busy = False
        self._session_busy = False
        self._latest_session_generation = 0
        self._latest_board_generation = 0
        self._latest_reserve_generation = 0
        self._latest_settings_generation = 0
        self._latest_poll_generation = 0
        self._is_closing = False

        self.polling_coordinator = PollingCoordinator(on_tick=self._polling_tick)
        self.polling_coordinator.state_changed.connect(self.apply_polling_state)

        self._build_ui()
        self._bind_controller()
        self._load_profiles()
        self.setWindowTitle("BUAA CGYY")
        self.resize(360, 240)
        self.show()

    def _bind_controller(self) -> None:
        if self.controller is None:
            return
        if hasattr(self.controller, "session_loaded"):
            self.controller.session_loaded.connect(self.handle_session_loaded)
        if hasattr(self.controller, "board_loaded"):
            self.controller.board_loaded.connect(self.handle_board_loaded)
        if hasattr(self.controller, "reserve_finished"):
            self.controller.reserve_finished.connect(self.handle_reserve_finished)
        if hasattr(self.controller, "settings_loaded"):
            self.controller.settings_loaded.connect(self.handle_settings_saved)
        if hasattr(self.controller, "lane_busy_changed"):
            self.controller.lane_busy_changed.connect(self._handle_lane_busy_changed)
        if hasattr(self.controller, "lane_failed"):
            self.controller.lane_failed.connect(self._handle_lane_failed)
        if hasattr(self.controller, "polling_state_changed"):
            self.controller.polling_state_changed.connect(self.apply_polling_state)

    def _build_ui(self) -> None:
        self.setStatusBar(QStatusBar(self))
        self.setStyleSheet(APP_QSS)

        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # 顶部工具栏
        self.top_toolbar = TopToolbar()
        self.profile_combo = self.top_toolbar.profile_combo
        root_layout.addWidget(self.top_toolbar)

        # 登录覆盖层（紧凑版）
        self.login_overlay = QFrame()
        self.login_overlay.setProperty("card", True)
        overlay_layout = QHBoxLayout(self.login_overlay)
        overlay_layout.setContentsMargins(8, 6, 8, 6)
        overlay_layout.setSpacing(6)
        self.login_hint = QLabel("未连接")
        self.login_hint.setProperty("role", "muted")
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("账号")
        self.login_username.setFixedWidth(80)
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("密码")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.setFixedWidth(80)
        self.login_button = QPushButton("连接")
        self.login_button.setProperty("variant", "secondary")
        self.login_button.setFixedHeight(28)
        overlay_layout.addWidget(self.login_hint)
        overlay_layout.addWidget(self.login_username)
        overlay_layout.addWidget(self.login_password)
        overlay_layout.addWidget(self.login_button)
        overlay_layout.addStretch(1)
        self.login_overlay.hide()
        root_layout.addWidget(self.login_overlay)

        # 参数卡片
        self.booking_card = BookingCard()
        root_layout.addWidget(self.booking_card)

        # 操作栏
        self.action_bar = ActionBar()
        root_layout.addWidget(self.action_bar)

        # 轮询状态（可隐藏）
        self.polling_summary = PollingSummary()
        self.polling_summary.hide()
        root_layout.addWidget(self.polling_summary)

        # 场地表格弹窗
        self.board_dialog = BoardDialog(self)
        self.board_table: QTableWidget = self.board_dialog.board_table
        self.board_table.cellClicked.connect(self._handle_cell_clicked)

        # 设置面板弹窗
        self.panel_dialog = PanelDialog(self)
        self.target_summary = self.panel_dialog.target_summary
        self.display_name_input = self.panel_dialog.display_name_input
        self.phone_input = self.panel_dialog.phone_input
        self.buddy_input = self.panel_dialog.buddy_input
        self.settings_site_input = self.panel_dialog.settings_site_input
        self.settings_date_input = self.panel_dialog.settings_date_edit
        self.settings_start_input = self.panel_dialog.settings_start_time_edit
        self.settings_slot_input = self.panel_dialog.settings_slot_input
        self.save_settings_button = self.panel_dialog.save_settings_button

        # 轮询弹窗
        self.poll_dialog = PollDialog(self)
        self.poll_dialog.start_button.clicked.connect(self._start_polling_from_dialog)

        # 信号绑定
        self.action_bar.reserve_button.clicked.connect(self._reserve_selected)
        self.action_bar.query_button.clicked.connect(self._refresh_board)
        self.action_bar.poll_button.clicked.connect(self._toggle_polling)
        self.action_bar.details_button.clicked.connect(self._toggle_board_dialog)
        self.profile_combo.currentIndexChanged.connect(self._handle_profile_combo_changed)
        self.top_toolbar.settings_button.clicked.connect(self._open_panel_dialog)
        self.login_button.clicked.connect(self._login_current_profile)
        self.save_settings_button.clicked.connect(self._save_settings)

    def _open_panel_dialog(self) -> None:
        self.panel_dialog.show()
        self.panel_dialog.raise_()
        self.panel_dialog.activateWindow()

    def _toggle_board_dialog(self) -> None:
        if self.board_dialog.isVisible():
            self.board_dialog.hide()
        else:
            self.board_dialog.show()
            self.board_dialog.raise_()

    def _load_profiles(self) -> None:
        profiles = self.facade.list_profiles()
        self.top_toolbar.clear_profiles()
        for item in profiles:
            self.top_toolbar.add_profile(item.display_name or item.name, item.name)
        if profiles:
            self.profile_combo.setCurrentIndex(0)
            if hasattr(self.facade, "load_profile_form"):
                self.apply_settings_state(self.facade.load_profile_form(profiles[0].name))
            if hasattr(self.controller, "request_session_probe") or hasattr(self.facade, "get_session_state"):
                self._handle_profile_changed(profiles[0].name)

    def _current_profile(self) -> str:
        return self.top_toolbar.current_profile_data() or "default"

    def _current_board_query(self) -> BoardQuery:
        values = self.booking_card.current_request_values()
        return BoardQuery(
            profile_name=self._current_profile(),
            venue_site_id=int(values["venue_site_id"]),
            date=str(values["date"]),
            start_time=str(values["start_time"]),
            slot_count=int(values["slot_count"]),
        )

    def _handle_profile_combo_changed(self, _index: int) -> None:
        self._handle_profile_changed(self._current_profile())

    def _handle_profile_changed(self, profile_name: str) -> None:
        if not profile_name or self._settings_busy:
            return
        if hasattr(self.facade, "load_profile_form"):
            self.apply_settings_state(self.facade.load_profile_form(profile_name))
        self.apply_selection_state(None)
        if hasattr(self.controller, "request_session_probe"):
            self._latest_session_generation = self.controller.request_session_probe(profile_name)
            self.set_session_busy("authenticating", True, "检查连接...")
            return
        if hasattr(self.facade, "get_session_state"):
            self.apply_session_state(self.facade.get_session_state(profile_name))
            if self.session_state and self.session_state.status is SessionStatus.AUTHENTICATED:
                self._refresh_board()

    def apply_session_state(self, state: SessionState) -> None:
        self.session_state = state
        self.top_toolbar.apply_session_state(state)
        if state.status is SessionStatus.AUTHENTICATED:
            self.login_overlay.hide()
        else:
            self.login_overlay.show()
        self._update_enabled_state()

    def apply_polling_state(self, state: PollingState) -> None:
        self.polling_state = state
        self.polling_summary.apply_state(state)
        running = state.status in {PollingStatus.RUNNING, PollingStatus.STARTING, PollingStatus.STOPPING}
        self.action_bar.set_polling_running(running)
        # PollingSummary 不再显示，轮询状态集成在 BookingCard 中
        self._update_enabled_state()

    def apply_board_state(self, state: BoardState) -> None:
        self.board_state = state
        sync_text = f"{state.last_sync_at or '-'}"
        self.top_toolbar.set_sync_text(sync_text)
        self.board_dialog.set_sync_text(sync_text)
        self._render_board_table()

    def _render_board_table(self) -> None:
        state = self.board_state
        if state is None:
            return
        self.board_table.clear()
        self.board_table.setRowCount(len(state.rows))
        self.board_table.setColumnCount(len(state.time_headers))
        self.board_table.setHorizontalHeaderLabels(state.time_headers)
        self.board_table.setVerticalHeaderLabels([row.space_name for row in state.rows])
        self._cell_lookup.clear()
        selected_slots = self._selected_slots()
        for row_index, row in enumerate(state.rows):
            for col_index, cell in enumerate(row.cells):
                key = (cell.space_id, cell.begin_time)
                item = QTableWidgetItem(self._cell_text(cell, key in selected_slots))
                item.setTextAlignment(Qt.AlignCenter)
                fg_color, bg_color = self._cell_colors(cell=cell, is_selected=key in selected_slots)
                item.setForeground(fg_color)
                item.setBackground(bg_color)
                self.board_table.setItem(row_index, col_index, item)
                self._cell_lookup[(row_index, col_index)] = cell
        self.board_table.resizeRowsToContents()

    def _selected_slots(self) -> set[tuple[int, str]]:
        if self.selection_state is None or self.board_state is None:
            return set()
        selected: set[tuple[int, str]] = set()
        for row in self.board_state.rows:
            if row.space_id != self.selection_state.space_id:
                continue
            for cell in row.cells:
                if self.selection_state.start_time <= cell.begin_time < self.selection_state.end_time:
                    selected.add((cell.space_id, cell.begin_time))
        return selected

    def _cell_text(self, cell: BoardCell, is_selected: bool) -> str:
        if is_selected:
            return "✓"
        if cell.status_text == "未知":
            return "-"
        return "○" if cell.is_available else "●"

    def _cell_colors(self, *, cell: BoardCell, is_selected: bool) -> tuple[QColor, QColor]:
        if is_selected:
            return QColor("#ffffff"), QColor("#0EA5A4")
        if cell.selectable:
            return QColor("#0C4A6E"), QColor("#E6F6F6")
        if cell.status_text == "未知":
            return QColor("#7A6F66"), QColor("#F5EEE8")
        if cell.is_available:
            return QColor("#5B6575"), QColor("#EEF4F8")
        return QColor("#8A4D4D"), QColor("#FEECEC")

    def apply_selection_state(self, state: SelectionState | None) -> None:
        self.selection_state = state
        summary = "未选择" if state is None else f"{state.space_name} {state.start_time}-{state.end_time}"
        self.booking_card.set_target_summary(summary)
        self.board_dialog.set_selection_summary(summary)
        self.panel_dialog.target_summary.setText(summary)
        if self.board_state is not None:
            self._render_board_table()
        self._update_enabled_state()

    def apply_settings_state(self, state: SettingsFormState) -> None:
        self.settings_state = state
        self.display_name_input.setText(state.display_name)
        self.phone_input.setText(state.phone)
        self.buddy_input.setText(state.buddy_ids)
        self.settings_site_input.setValue(state.venue_site_id)
        self.settings_slot_input.setValue(state.slot_count)
        self._set_date_value(self.settings_date_input, state.default_search_date)
        self._set_time_value(self.settings_start_input, state.start_time)
        self.booking_card.set_values(
            date=state.default_search_date,
            start_time=state.start_time,
            slot_count=state.slot_count,
            venue_site_id=state.venue_site_id,
        )

    def _set_date_value(self, widget, value: str) -> None:
        parsed = QDate.fromString(value, "yyyy-MM-dd")
        widget.setDate(parsed if parsed.isValid() else QDate.currentDate())

    def _set_time_value(self, widget, value: str) -> None:
        parsed = QTime.fromString(value, "HH:mm")
        widget.setTime(parsed if parsed.isValid() else QTime(18, 0))

    def _refresh_board(self) -> None:
        query = self._current_board_query()
        if hasattr(self.controller, "request_board_refresh"):
            self._latest_board_generation = self.controller.request_board_refresh(query)
            self.set_board_busy(True, "同步中...")
            return
        try:
            self.apply_board_state(self.facade.load_board(query))
            self.statusBar().showMessage("查询成功", 3000)
        except Exception as exc:
            self.statusBar().showMessage(str(exc), 5000)

    def _polling_tick(self, query: BoardQuery) -> None:
        if self.session_state is None or self.session_state.status is not SessionStatus.AUTHENTICATED:
            return
        if hasattr(self.controller, "request_board_refresh"):
            self._latest_board_generation = self.controller.request_board_refresh(query)
            return
        try:
            self.apply_board_state(self.facade.load_board(query))
        except Exception:
            return

    def _handle_cell_clicked(self, row: int, column: int) -> None:
        if self._reserve_busy or self._board_busy:
            return
        cell = self._cell_lookup.get((row, column))
        if cell is None or self.board_state is None or not cell.selectable:
            self.apply_selection_state(None)
            return
        row_state = self.board_state.rows[row]
        start_idx = next((idx for idx, item in enumerate(row_state.cells) if item.time_id == cell.time_id), 0)
        end_idx = min(start_idx + self.board_state.slot_count - 1, len(row_state.cells) - 1)
        end_cell = row_state.cells[end_idx]
        self.apply_selection_state(
            SelectionState(
                space_id=cell.space_id,
                space_name=cell.space_name,
                start_time=cell.begin_time,
                end_time=end_cell.end_time,
                slot_count=self.board_state.slot_count,
            )
        )

    def _login_current_profile(self) -> None:
        if hasattr(self.controller, "request_login"):
            generation = self.controller.request_login(
                self._current_profile(),
                self.login_username.text().strip(),
                self.login_password.text().strip(),
            )
            if generation is not None:
                self._latest_session_generation = generation
                self.set_session_busy("authenticating", True, "连接中...")
            return
        try:
            state = self.facade.login(
                self._current_profile(),
                self.login_username.text().strip(),
                self.login_password.text().strip(),
            )
            self.apply_session_state(state)
            self._refresh_board()
            self.statusBar().showMessage("连接成功", 3000)
        except Exception as exc:
            self.statusBar().showMessage(str(exc), 5000)

    def _save_settings(self) -> None:
        state = SettingsFormState(
            profile_name=self._current_profile(),
            display_name=self.display_name_input.text().strip(),
            phone=self.phone_input.text().strip(),
            buddy_ids=self.buddy_input.text().strip(),
            venue_site_id=self.settings_site_input.value(),
            default_search_date=self.settings_date_input.date().toString("yyyy-MM-dd"),
            start_time=self.settings_start_input.time().toString("HH:mm"),
            slot_count=self.settings_slot_input.value(),
        )
        if hasattr(self.controller, "request_save_settings"):
            generation = self.controller.request_save_settings(state)
            if generation is not None:
                self._latest_settings_generation = generation
                self.set_settings_busy(True, "保存中...")
            return
        self.apply_settings_state(self.facade.save_profile_patch(state))
        self.statusBar().showMessage("配置已保存", 3000)

    def _toggle_polling(self) -> None:
        running = self.polling_state.status in {PollingStatus.RUNNING, PollingStatus.STARTING, PollingStatus.STOPPING}
        if running:
            if hasattr(self.controller, "request_stop_polling"):
                generation = self.controller.request_stop_polling()
                if generation is not None:
                    self._latest_poll_generation = generation
            self.polling_coordinator.stop()
            return

        # 显示轮询弹窗（底部非模态）
        self.poll_dialog.show_at_bottom()

    def _start_polling_from_dialog(self) -> None:
        """从轮询弹窗开始轮询"""
        self.poll_dialog.hide()

        if self._board_busy:
            return

        query = self._current_board_query()
        accepted = True
        if hasattr(self.controller, "request_start_polling"):
            generation = self.controller.request_start_polling(query)
            accepted = generation is not None
            if accepted:
                self._latest_poll_generation = generation
        if accepted:
            self.polling_coordinator.start(query)

    def _reserve_selected(self) -> None:
        if self.selection_state is None or self.board_state is None:
            return
        request = ReserveRequest(
            profile_name=self._current_profile(),
            venue_site_id=self.booking_card.venue_site_id(),
            date=self.board_state.date,
            space_id=self.selection_state.space_id,
            start_time=self.selection_state.start_time,
            slot_count=self.selection_state.slot_count,
        )
        if hasattr(self.controller, "request_reserve"):
            generation = self.controller.request_reserve(request)
            if generation is not None:
                self._latest_reserve_generation = generation
                self.set_reserve_busy(True, "预约中...")
            return
        try:
            result: ReserveOutcome = self.facade.reserve(request)
            message = result.message or "预约完成"
            if result.trade_no:
                message = f"{message} / {result.trade_no}"
            self.statusBar().showMessage(message, 5000)
        except Exception as exc:
            self.statusBar().showMessage(str(exc), 5000)

    def set_board_busy(self, busy: bool, message: str = "") -> None:
        self._board_busy = busy
        if message:
            self.statusBar().showMessage(message, 0 if busy else 3000)
        self._update_enabled_state()

    def set_reserve_busy(self, busy: bool, message: str = "") -> None:
        self._reserve_busy = busy
        if message:
            self.statusBar().showMessage(message, 0 if busy else 3000)
        self._update_enabled_state()

    def set_settings_busy(self, busy: bool, message: str = "") -> None:
        self._settings_busy = busy
        if message:
            self.statusBar().showMessage(message, 0 if busy else 3000)
        self._update_enabled_state()

    def set_session_busy(self, mode: str, busy: bool, message: str = "") -> None:
        self._session_busy = busy
        self.login_username.setEnabled(not busy)
        self.login_password.setEnabled(not busy)
        self.login_button.setEnabled(not busy)
        if message:
            self.statusBar().showMessage(message, 0 if busy else 3000)
        self._update_enabled_state()

    def _update_enabled_state(self) -> None:
        authed = bool(self.session_state and self.session_state.status is SessionStatus.AUTHENTICATED)
        polling_active = self.polling_state.status in {
            PollingStatus.RUNNING,
            PollingStatus.STARTING,
            PollingStatus.STOPPING,
        }
        can_reserve = bool(
            authed
            and self.selection_state is not None
            and not self._board_busy
            and not self._reserve_busy
            and not self._session_busy
            and not polling_active
        )
        can_query = bool(authed and not self._board_busy and not self._reserve_busy and not self._session_busy and not polling_active)
        self.action_bar.reserve_button.setEnabled(can_reserve)
        self.action_bar.query_button.setEnabled(can_query)
        self.action_bar.poll_button.setEnabled(
            authed and not self._reserve_busy and not self._session_busy and not self._board_busy
        )
        self.top_toolbar.profile_combo.setEnabled(not self._settings_busy and not self._session_busy)
        self.save_settings_button.setEnabled(not self._settings_busy)

    def _handle_lane_busy_changed(self, lane: str, busy: bool) -> None:
        if lane == "session":
            self.set_session_busy("authenticating" if busy else "", busy, "连接中..." if busy else "")
        elif lane == "board":
            self.set_board_busy(busy, "同步中..." if busy else "")
        elif lane == "reserve":
            self.set_reserve_busy(busy, "预约中..." if busy else "")
        elif lane == "settings":
            self.set_settings_busy(busy, "保存中..." if busy else "")

    def _handle_lane_failed(self, lane: str, generation: int, message: str) -> None:
        if lane == "session" and generation != self._latest_session_generation:
            return
        if lane == "board" and generation != self._latest_board_generation:
            return
        if lane == "reserve" and generation != self._latest_reserve_generation:
            return
        if lane == "settings" and generation != self._latest_settings_generation:
            return
        if lane == "session":
            self.set_session_busy("", False)
        elif lane == "board":
            self.set_board_busy(False)
        elif lane == "reserve":
            self.set_reserve_busy(False)
        elif lane == "settings":
            self.set_settings_busy(False)
        self.statusBar().showMessage(message, 5000)

    def handle_session_loaded(self, generation: int, state: SessionState) -> None:
        if self._is_closing or generation < self._latest_session_generation:
            return
        self._latest_session_generation = generation
        self.set_session_busy("", False)
        self.apply_session_state(state)
        if state.status is SessionStatus.AUTHENTICATED:
            self._refresh_board()

    def handle_board_loaded(self, generation: int, state: BoardState) -> None:
        if self._is_closing or generation < self._latest_board_generation:
            return
        self._latest_board_generation = generation
        self.set_board_busy(False)
        self.apply_board_state(state)
        if self.polling_state.status is PollingStatus.RUNNING:
            self.apply_polling_state(
                PollingState(
                    status=PollingStatus.RUNNING,
                    interval_sec=self.polling_state.interval_sec,
                    last_checked_at=state.last_sync_at,
                    last_message="检查完成",
                )
            )
        self.statusBar().showMessage("查询成功", 3000)

    def handle_reserve_finished(self, generation: int, result: ReserveOutcome) -> None:
        if self._is_closing or generation != self._latest_reserve_generation:
            return
        self.set_reserve_busy(False)
        message = result.message or "预约完成"
        if result.trade_no:
            message = f"{message} / {result.trade_no}"
        self.statusBar().showMessage(message, 5000)

    def handle_settings_saved(self, generation: int, state: SettingsFormState) -> None:
        if self._is_closing or generation != self._latest_settings_generation:
            return
        self.set_settings_busy(False)
        self.apply_settings_state(state)
        self.statusBar().showMessage("配置已保存", 3000)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._is_closing = True
        self.polling_coordinator.stop()
        if self.poll_dialog.isVisible():
            self.poll_dialog.hide()
        if self.panel_dialog.isVisible():
            self.panel_dialog.close()
        if self.board_dialog.isVisible():
            self.board_dialog.close()
        super().closeEvent(event)
