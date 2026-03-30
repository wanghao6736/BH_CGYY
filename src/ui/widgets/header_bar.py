from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class HeaderBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)

        self.title_label = QLabel("CGYY Workbench")
        self.title_label.setObjectName("windowTitle")
        self.subtitle_label = QLabel("小巧预约工具")
        self.subtitle_label.setObjectName("windowSubtitle")
        self.subtitle_label.setProperty("muted", True)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(2)
        title_stack.addWidget(self.title_label)
        title_stack.addWidget(self.subtitle_label)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(168)
        self.auth_badge = QLabel("未连接")
        self.auth_badge.setProperty("badge", True)
        self.sync_badge = QLabel("未同步")
        self.sync_badge.setProperty("muted", True)
        self.panel_button = QPushButton("面板")
        self.panel_button.setObjectName("secondaryAction")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        layout.addLayout(title_stack, 1)
        layout.addWidget(self.profile_combo)
        layout.addWidget(self.auth_badge)
        layout.addWidget(self.sync_badge)
        layout.addWidget(self.panel_button)
