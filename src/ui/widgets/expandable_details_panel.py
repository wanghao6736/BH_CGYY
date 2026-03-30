from __future__ import annotations

from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QTableWidget,
                               QVBoxLayout, QWidget)


class ExpandableDetailsPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)
        self._expanded = False
        self._last_animation = None

        self.title_label = QLabel("时段详情")
        self.title_label.setProperty("role", "subtitle")
        self.sync_label = QLabel("未同步")
        self.sync_label.setProperty("role", "subtitle")

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(self.title_label)
        top_row.addStretch(1)
        top_row.addWidget(self.sync_label)

        self.content_container = QWidget()
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        self.board_table = QTableWidget()
        self.selection_summary = QLabel("未选择目标")
        self.selection_summary.setProperty("summary", "true")
        content_layout.addWidget(self.board_table)
        content_layout.addWidget(self.selection_summary)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        layout.addLayout(top_row)
        layout.addWidget(self.content_container)

        self.set_expanded(False)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.content_container.setVisible(expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_selection_summary(self, text: str) -> None:
        self.selection_summary.setText(text or "未选择目标")
