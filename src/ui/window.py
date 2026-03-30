from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QPushButton, QStatusBar,
                               QVBoxLayout, QWidget)

from src.ui.animations import build_expand_animation
from src.ui.facade import BoardQuery, ReserveRequest
from src.ui.polling import PollingCoordinator
from src.ui.state import (BoardCell, BoardState, PollingState, PollingStatus,
                          ReserveOutcome, SelectionState, SessionState,
                          SessionStatus, SettingsFormState)
from src.ui.theme import APP_QSS
from src.ui.widgets import (ActionBar, BookingCard, PanelDialog, PollDialog,
                            PollingSummary, TopToolbar)
from src.ui.widgets.board_panel import BoardPanel
from src.ui.widgets.heatmap_widget import CellStatus, HeatCell


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

        # 详情热力图面板
        self.board_panel = BoardPanel(self)
        self.heatmap = self.board_panel.heatmap
        self.heatmap.cellClicked.connect(self._handle_heatmap_cell_clicked)

        # 设置面板弹窗
        self.panel_dialog = PanelDialog(self)
        self.target_summary = self.panel_dialog.target_summary
        self.display_name_input = self.panel_dialog.display_name_input
        self.phone_input = self.panel_dialog.phone_input
        self.buddy_input = self.panel_dialog.buddy_input
        self.settings_site_input = self.panel_dialog.settings_site_input
        self.settings_date_input = self.panel_dialog.settings_date_input
        self.settings_start_input = self.panel_dialog.settings_start_input
        self.settings_slot_input = self.panel_dialog.settings_slot_input
        self.save_settings_button = self.panel_dialog.save_settings_button

        # 轮询弹窗
        self.poll_dialog = PollDialog(self)
        self.poll_dialog.start_button.clicked.connect(self._start_polling_from_dialog)

        # 信号绑定
        self.action_bar.reserve_button.clicked.connect(self._reserve_selected)
        self.action_bar.query_button.clicked.connect(self._refresh_board)
        self.action_bar.poll_button.clicked.connect(self._toggle_polling)
        self.action_bar.details_button.clicked.connect(self._toggle_board_panel)
        self.profile_combo.currentIndexChanged.connect(self._handle_profile_combo_changed)
        self.top_toolbar.settings_button.clicked.connect(self._open_panel_dialog)
        self.login_button.clicked.connect(self._login_current_profile)
        self.save_settings_button.clicked.connect(self._save_settings)

    def _open_panel_dialog(self) -> None:
        self.panel_dialog.show()
        self.panel_dialog.raise_()
        self.panel_dialog.activateWindow()

    def _toggle_board_panel(self) -> None:
        if self.board_panel.isVisible():
            self.board_panel.hide()
        else:
            self.board_panel.show_at_bottom()

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
        self.board_panel.set_sync_text(sync_text)
        self._render_heatmap()

    def _map_cell_status(self, cell: BoardCell) -> CellStatus:
        """将 BoardCell 状态映射到热力图状态"""
        if cell.status_text == "未知":
            return CellStatus.UNKNOWN
        if not cell.is_available:
            return CellStatus.RESERVED
        if cell.selectable:
            return CellStatus.AVAILABLE
        return CellStatus.LOCKED

    def _render_heatmap(self) -> None:
        """渲染热力图"""
        state = self.board_state
        if state is None:
            return

        rows = len(state.rows)
        cols = len(state.time_headers) if state.time_headers else 0
        self.heatmap.set_dimensions(rows, cols)

        # 设置表头
        self.heatmap.set_headers(
            row_headers=[row.space_name for row in state.rows],
            col_headers=state.time_headers
        )

        # 设置单元格数据
        selected_slots = self._selected_slots()
        for row_index, row in enumerate(state.rows):
            for col_index, cell in enumerate(row.cells):
                key = (cell.space_id, cell.begin_time)
                heat_cell = HeatCell(
                    status=self._map_cell_status(cell),
                    enabled=cell.selectable,
                    selected=key in selected_slots,
                    tooltip=f"{cell.space_name} {cell.begin_time}-{cell.end_time}"
                )
                self.heatmap.set_cell(row_index, col_index, heat_cell)

        # 更新选择摘要
        if self.selection_state:
            summary = f"{self.selection_state.space_name} {self.selection_state.start_time}-{self.selection_state.end_time}"
        else:
            summary = "点击单元格选择时段"
        self.board_panel.set_selection_summary(summary)

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

    def apply_selection_state(self, state: SelectionState | None) -> None:
        self.selection_state = state
        summary = "未选择" if state is None else f"{state.space_name} {state.start_time}-{state.end_time}"
        self.booking_card.set_target_summary(summary)
        self.board_panel.set_selection_summary(summary)
        self.panel_dialog.target_summary.setText(summary)
        if self.board_state is not None:
            self._render_heatmap()
        self._update_enabled_state()

    def apply_settings_state(self, state: SettingsFormState) -> None:
        self.settings_state = state
        self.display_name_input.setText(state.display_name)
        self.phone_input.setText(state.phone)
        self.buddy_input.setText(state.buddy_ids)
        self.settings_site_input.setText(str(state.venue_site_id))
        self.settings_slot_input.setCurrentIndex(max(0, min(state.slot_count - 1, 5)))
        self._set_date_combo_value(self.settings_date_input, state.default_search_date)
        self._set_time_combo_value(self.settings_start_input, state.start_time)
        self.booking_card.set_values(
            date=state.default_search_date,
            start_time=state.start_time,
            slot_count=state.slot_count,
            venue_site_id=state.venue_site_id,
        )

    def _set_date_combo_value(self, combo, value: str) -> None:
        """设置日期下拉框的值"""
        parsed = QDate.fromString(value, "yyyy-MM-dd")
        if not parsed.isValid():
            combo.setCurrentIndex(0)
            return

        today = QDate.currentDate()
        days_diff = today.daysTo(parsed)

        if days_diff == 0:
            combo.setCurrentIndex(0)  # 今天
        elif days_diff == 1:
            combo.setCurrentIndex(1)  # 明天
        elif 0 <= days_diff < 7:
            combo.setCurrentIndex(days_diff)
        else:
            combo.setCurrentIndex(0)

    def _set_time_combo_value(self, combo, value: str) -> None:
        """设置时间下拉框的值"""
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(20)  # 默认 18:00

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

    def _handle_heatmap_cell_clicked(self, row: int, col: int) -> None:
        """处理热力图单元格点击"""
        if self._reserve_busy or self._board_busy:
            return
        if self.board_state is None or row >= len(self.board_state.rows):
            self.apply_selection_state(None)
            return

        row_state = self.board_state.rows[row]
        if col >= len(row_state.cells):
            self.apply_selection_state(None)
            return

        cell = row_state.cells[col]
        if not cell.selectable:
            self.apply_selection_state(None)
            return

        start_idx = col
        end_idx = min(start_idx + self.board_state.slot_count - 1, len(row_state.cells) - 1)
        
        # 检查范围内所有单元格是否都可选
        for i in range(start_idx, end_idx + 1):
            if not row_state.cells[i].selectable:
                self.apply_selection_state(None)
                return
        
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

    def _handle_cell_clicked(self, row: int, column: int) -> None:
        """处理表格单元格点击（已弃用，保留兼容）"""
        pass

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
        # 解析场地ID
        try:
            venue_site_id = int(self.settings_site_input.text().strip() or "57")
        except ValueError:
            venue_site_id = 57

        # 解析日期
        date_text = self.settings_date_input.currentText()
        if date_text == "今天":
            default_date = QDate.currentDate().toString("yyyy-MM-dd")
        elif date_text == "明天":
            default_date = QDate.currentDate().addDays(1).toString("yyyy-MM-dd")
        else:
            # MM-dd 格式
            month, day = map(int, date_text.split("-"))
            today = QDate.currentDate()
            candidate = QDate(today.year(), month, day)
            if candidate.isValid() and candidate < today:
                candidate = candidate.addYears(1)
            default_date = candidate.toString("yyyy-MM-dd") if candidate.isValid() else today.toString("yyyy-MM-dd")

        state = SettingsFormState(
            profile_name=self._current_profile(),
            display_name=self.display_name_input.text().strip(),
            phone=self.phone_input.text().strip(),
            buddy_ids=self.buddy_input.text().strip(),
            venue_site_id=venue_site_id,
            default_search_date=default_date,
            start_time=self.settings_start_input.currentText(),
            slot_count=self.settings_slot_input.currentIndex() + 1,
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
        if self.board_panel.isVisible():
            self.board_panel.close()
        super().closeEvent(event)
