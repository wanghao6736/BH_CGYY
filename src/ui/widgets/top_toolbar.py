from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.ui.state import SessionState, SessionStatus
from src.ui.widgets.custom_combo import CustomComboBox


class TopToolbar(QFrame):
    """顶部状态栏：品牌标识、配置切换、状态指示、设置按钮"""

    profileChanged = Signal(int)
    logoutRequested = Signal()
    settingsRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("topToolbar", "true")
        self._sync_text = ""

        # 品牌标识
        self.title_label = QLabel("✈️ BUAA CGYY")
        self.title_label.setProperty("role", "title")

        # 配置下拉 (使用 CustomComboBox，支持关联数据)
        self.profile_combo = CustomComboBox()
        self.profile_combo.setMinimumWidth(80)
        self.profile_combo.setMaximumWidth(120)

        # 状态圆点
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setProperty("statusDot", "error")

        # 同步时间
        self.sync_label = QLabel("")
        self.sync_label.setProperty("role", "muted")

        # 退出按钮
        self.logout_button = QPushButton("⏏️ 退出")
        self.logout_button.setProperty("variant", "ghost")
        self.logout_button.setMinimumWidth(40)
        self.logout_button.setToolTip("退出当前 profile")
        self.logout_button.setEnabled(False)

        # 设置按钮
        self.settings_button = QPushButton("⚙️ 设置")
        self.settings_button.setProperty("variant", "toolbar")
        self.settings_button.setToolTip("设置")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 5)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.profile_combo)
        layout.addStretch(1)
        layout.addWidget(self.status_dot)
        layout.addWidget(self.sync_label)
        layout.addWidget(self.logout_button)
        layout.addWidget(self.settings_button)

        self.profile_combo.currentIndexChanged.connect(self.profileChanged.emit)
        self.logout_button.clicked.connect(self.logoutRequested.emit)
        self.settings_button.clicked.connect(self.settingsRequested.emit)

    def _update_status_dot(self, status: SessionStatus) -> None:
        """更新状态圆点颜色"""
        if status is SessionStatus.AUTHENTICATED:
            self.status_dot.setProperty("statusDot", "ok")
        elif status in (SessionStatus.AUTHENTICATING, SessionStatus.PROBING):
            self.status_dot.setProperty("statusDot", "active")
        else:
            self.status_dot.setProperty("statusDot", "error")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)

    def apply_session_state(self, state: SessionState) -> None:
        self._update_status_dot(state.status)
        self.sync_label.setText(self._sync_text)
        self.logout_button.setEnabled(state.status is SessionStatus.AUTHENTICATED)

    def set_sync_text(self, text: str) -> None:
        self._sync_text = text or ""
        self.sync_label.setText(self._sync_text)

    def set_profiles(self, items: list[tuple[str, Any]]) -> None:
        """批量设置配置项。"""
        self.profile_combo.clear()
        for name, data in items:
            self.profile_combo.addItem(name, data)

    def set_current_profile_index(self, index: int) -> None:
        self.profile_combo.setCurrentIndex(index)

    def set_profiles_enabled(self, enabled: bool) -> None:
        self.profile_combo.setEnabled(enabled)

    def set_logout_enabled(self, enabled: bool) -> None:
        self.logout_button.setEnabled(enabled)

    def current_profile_data(self) -> Any:
        """获取当前配置关联的数据。"""
        return self.profile_combo.currentData()
