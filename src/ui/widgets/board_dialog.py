from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QTableWidget,
                               QVBoxLayout, QWidget)


class BoardDialog(QDialog):
    """场地时段表格弹窗"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("boardDialog", "true")
        self.setWindowTitle("时段详情")
        self.resize(480, 380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)

        # 标题栏
        self.title_label = QLabel("时段详情")
        self.title_label.setProperty("role", "subtitle")

        self.sync_label = QLabel("未同步")
        self.sync_label.setProperty("role", "muted")

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(self.title_label)
        top_row.addStretch(1)
        top_row.addWidget(self.sync_label)

        # 表格
        self.board_table = QTableWidget()
        self.board_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.board_table.setSelectionMode(QTableWidget.NoSelection)
        self.board_table.verticalHeader().setDefaultSectionSize(32)
        self.board_table.horizontalHeader().setDefaultSectionSize(56)
        self.board_table.horizontalHeader().setMinimumSectionSize(48)
        self.board_table.verticalHeader().setMinimumSectionSize(28)

        # 选择摘要
        self.selection_summary = QLabel("点击单元格选择时段")
        self.selection_summary.setProperty("summary", "true")

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addLayout(top_row)
        layout.addWidget(self.board_table, 1)
        layout.addWidget(self.selection_summary)

    def set_selection_summary(self, text: str) -> None:
        self.selection_summary.setText(text or "点击单元格选择时段")

    def set_sync_text(self, text: str) -> None:
        self.sync_label.setText(text or "未同步")