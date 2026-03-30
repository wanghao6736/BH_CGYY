from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton


class ActionBar(QFrame):
    """操作栏：详情、刷新、轮询、预约按钮"""

    detailsRequested = Signal()
    queryRequested = Signal()
    pollRequested = Signal()
    reserveRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("action_bar", "true")

        # 详情按钮
        self.details_button = QPushButton("📄 详情")
        self.details_button.setProperty("variant", "secondary")
        self.details_button.setFixedHeight(28)

        # 刷新按钮
        self.query_button = QPushButton("🔄 刷新")
        self.query_button.setProperty("variant", "secondary")
        self.query_button.setFixedHeight(28)

        # 轮询按钮
        self.poll_button = QPushButton("🔂 轮询")
        self.poll_button.setProperty("variant", "warning")
        self.poll_button.setFixedHeight(28)

        # 预约按钮
        self.reserve_button = QPushButton("🎯 立即预约")
        self.reserve_button.setProperty("variant", "primary")
        self.reserve_button.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        layout.addWidget(self.details_button)
        layout.addWidget(self.query_button)
        layout.addWidget(self.poll_button)
        layout.addStretch(1)
        layout.addWidget(self.reserve_button)

        self.details_button.clicked.connect(self.detailsRequested.emit)
        self.query_button.clicked.connect(self.queryRequested.emit)
        self.poll_button.clicked.connect(self.pollRequested.emit)
        self.reserve_button.clicked.connect(self.reserveRequested.emit)

    def set_query_enabled(self, enabled: bool) -> None:
        self.query_button.setEnabled(enabled)

    def set_poll_enabled(self, enabled: bool) -> None:
        self.poll_button.setEnabled(enabled)

    def set_reserve_enabled(self, enabled: bool) -> None:
        self.reserve_button.setEnabled(enabled)

    def set_polling_running(self, running: bool) -> None:
        """设置轮询状态"""
        if running:
            self.poll_button.setText("🛑 停止")
            self.poll_button.setProperty("active", "true")
        else:
            self.poll_button.setText("🔂 轮询")
            self.poll_button.setProperty("active", "false")
        # 刷新样式
        self.poll_button.style().unpolish(self.poll_button)
        self.poll_button.style().polish(self.poll_button)
