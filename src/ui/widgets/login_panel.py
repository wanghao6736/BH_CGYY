from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QPushButton,
                               QVBoxLayout, QWidget)

from src.ui.state import LoginFormState, SessionState, SessionStatus
from src.ui.styles import load_stylesheet
from src.ui.widgets.custom_combo import CustomComboBox


class LoginWindow(QMainWindow):
    authenticated = Signal(str)

    def __init__(self, facade, *, controller, initial_profile_name: str |
                 None = None, show_on_init: bool = True) -> None:
        super().__init__()
        self.facade = facade
        self.controller = controller
        self.initial_profile_name = initial_profile_name
        self.login_state: LoginFormState | None = None
        self.session_state: SessionState | None = None
        self._persist_mode_text = ""
        self._session_busy = False
        self._latest_session_generation = 0
        self._is_closing = False

        self._build_ui()
        self._bind_controller()
        self._load_profiles()
        self.setWindowTitle("BUAA CGYY 登录")
        self.setFixedSize(360, 236)
        if show_on_init:
            self.show()

    def _build_ui(self) -> None:
        self.setStyleSheet(load_stylesheet())

        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setProperty("card", True)
        root_layout.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        self.profile_combo = CustomComboBox()
        self.profile_combo.setMinimumWidth(136)
        self.profile_combo.setFixedHeight(30)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("🤖 账号")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("🗝️ 密码")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.persist_auth_checkbox = QCheckBox("🔒 保持登录")
        self.hint_label = QLabel("请选择 profile")
        self.hint_label.setProperty("role", "muted")
        self.hint_label.setWordWrap(True)
        self.hint_label.setMinimumHeight(28)
        self.hint_label.setContentsMargins(2, 0, 2, 0)
        self.login_button = QPushButton("🔑 登录")
        self.login_button.setProperty("variant", "primary")
        self.login_button.setMinimumSize(56, 30)
        self.login_button.setMaximumSize(56, 30)

        profile_row = QHBoxLayout()
        profile_row.setContentsMargins(0, 0, 0, 0)
        profile_row.setSpacing(8)
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(self.persist_auth_checkbox)
        profile_row.addStretch(1)
        profile_row.addWidget(self.login_button)

        card_layout.addWidget(self.hint_label)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(self.password_input)
        card_layout.addStretch(1)
        card_layout.addLayout(profile_row)

        self.profile_combo.currentIndexChanged.connect(self._handle_profile_combo_changed)
        self.persist_auth_checkbox.toggled.connect(self._handle_persist_auth_toggled)
        self.login_button.clicked.connect(self._login_current_profile)
        self.password_input.returnPressed.connect(self._login_current_profile)

    def _bind_controller(self) -> None:
        self.controller.session_loaded.connect(self._handle_session_loaded)
        self.controller.lane_busy_changed.connect(self._handle_lane_busy_changed)
        self.controller.lane_failed.connect(self._handle_lane_failed)

    def _load_profiles(self) -> None:
        profiles = self.facade.list_profiles()
        self.profile_combo.setItemsWithData(
            [(item.display_name or item.name, item.name) for item in profiles]
        )
        if not profiles:
            self.hint_label.setText("未找到可用 profile")
            self._set_session_busy(False)
            return
        target_name = self.initial_profile_name or profiles[0].name
        index = next((i for i, item in enumerate(profiles) if item.name == target_name), 0)
        self.profile_combo.setCurrentIndex(index)
        self._apply_login_form_state(self.facade.load_login_form(self.current_profile()))
        self._probe_session(self.current_profile())

    def current_profile(self) -> str:
        return self.profile_combo.currentData() or "default"

    def _apply_login_form_state(self, state: LoginFormState) -> None:
        self.login_state = state
        self.username_input.setText(state.username)
        self.password_input.clear()
        self.persist_auth_checkbox.setChecked(state.persist_auth)
        self._update_persist_hint()

    def _update_persist_hint(self) -> None:
        if self.persist_auth_checkbox.isChecked():
            self._persist_mode_text = "登录后保持登录"
        else:
            self._persist_mode_text = "仅当前会话"
        if not self._session_busy:
            self.hint_label.setText(f"请输入账号密码，{self._persist_mode_text}")

    def _set_session_busy(self, busy: bool, message: str = "") -> None:
        self._session_busy = busy
        self.profile_combo.setEnabled(not busy)
        self.username_input.setEnabled(not busy)
        self.password_input.setEnabled(not busy)
        self.persist_auth_checkbox.setEnabled(not busy)
        self.login_button.setEnabled(not busy)
        if message:
            self.hint_label.setText(message)

    def _probe_session(self, profile_name: str) -> None:
        if not profile_name:
            return
        self._latest_session_generation = self.controller.request_session_probe(profile_name)
        self._set_session_busy(True, "检查连接...")

    def _handle_profile_combo_changed(self, _index: int) -> None:
        profile_name = self.current_profile()
        self._apply_login_form_state(self.facade.load_login_form(profile_name))
        self._probe_session(profile_name)

    def _handle_persist_auth_toggled(self, _checked: bool) -> None:
        self._update_persist_hint()

    def _login_current_profile(self) -> None:
        generation = self.controller.request_login(
            self.current_profile(),
            self.username_input.text().strip(),
            self.password_input.text().strip(),
            persist_auth=self.persist_auth_checkbox.isChecked(),
        )
        if generation is None:
            return
        self._latest_session_generation = generation
        self._set_session_busy(True, "连接中...")

    def _handle_lane_busy_changed(self, lane: str, busy: bool) -> None:
        if lane != "session":
            return
        self._set_session_busy(busy, "连接中..." if busy else "")

    def _handle_lane_failed(self, lane: str, generation: int, message: str) -> None:
        if lane != "session" or generation != self._latest_session_generation:
            return
        self._set_session_busy(False)
        self.hint_label.setText(message)

    def _handle_session_loaded(self, generation: int, state: SessionState) -> None:
        if self._is_closing or generation < self._latest_session_generation:
            return
        self._latest_session_generation = generation
        self.session_state = state
        self._set_session_busy(False)
        if state.status is SessionStatus.AUTHENTICATED:
            self.password_input.clear()
            self.hint_label.setText("登录成功，正在进入首页...")
            self.authenticated.emit(state.profile_name)
            return
        self.hint_label.setText(f"{state.message or '需要重新登录'}，{self._persist_mode_text}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._is_closing = True
        super().closeEvent(event)
