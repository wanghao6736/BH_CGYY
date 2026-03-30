from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from src.ui.state import PollingState, PollingStatus


class PollingSummary(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)

        self.status_badge = QLabel("已停止")
        self.status_badge.setProperty("badge", True)
        self.status_badge.setProperty("badge_variant", "polling")

        self.message_label = QLabel("未启动")
        self.message_label.setProperty("role", "subtitle")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(self.status_badge)
        layout.addWidget(self.message_label, 1)

    def apply_state(self, state: PollingState) -> None:
        if state.status is PollingStatus.RUNNING:
            self.status_badge.setText("轮询中")
        elif state.status is PollingStatus.STARTING:
            self.status_badge.setText("启动中")
        elif state.status is PollingStatus.STOPPING:
            self.status_badge.setText("停止中")
        elif state.status is PollingStatus.ERROR:
            self.status_badge.setText("异常")
        else:
            self.status_badge.setText("已停止")

        suffix = f" · {state.last_checked_at}" if state.last_checked_at else ""
        self.message_label.setText(f"{state.last_message}{suffix}".strip())
