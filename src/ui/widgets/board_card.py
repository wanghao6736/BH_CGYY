from __future__ import annotations

from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QTableWidget,
                               QVBoxLayout)


class BoardCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)

        self.title_label = QLabel("可预约时段")
        self.title_label.setObjectName("sectionTitle")
        self.venue_label = QLabel("未选择场馆")
        self.venue_label.setProperty("muted", True)
        self.sync_label = QLabel("未同步")
        self.sync_label.setProperty("muted", True)

        self.legend_available = QLabel("可选")
        self.legend_available.setProperty("legend", "available")
        self.legend_occupied = QLabel("占用")
        self.legend_occupied.setProperty("legend", "occupied")
        self.legend_unknown = QLabel("未知")
        self.legend_unknown.setProperty("legend", "unknown")

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)
        top_row.addWidget(self.title_label)
        top_row.addWidget(self.venue_label, 1)
        top_row.addWidget(self.sync_label)

        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(0, 0, 0, 0)
        legend_row.setSpacing(8)
        legend_row.addWidget(self.legend_available)
        legend_row.addWidget(self.legend_occupied)
        legend_row.addWidget(self.legend_unknown)
        legend_row.addStretch(1)

        self.board_table = QTableWidget()
        self.board_table.setObjectName("availabilityTable")
        self.selection_summary = QLabel("未选择目标")
        self.selection_summary.setObjectName("selectionSummary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addLayout(top_row)
        layout.addLayout(legend_row)
        layout.addWidget(self.board_table, 1)
        layout.addWidget(self.selection_summary)

    def set_selection_summary(self, text: str) -> None:
        self.selection_summary.setText(text or "未选择目标")
