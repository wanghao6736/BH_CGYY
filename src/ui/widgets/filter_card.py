from __future__ import annotations

from PySide6.QtCore import QDate, QTime, Signal
from PySide6.QtWidgets import (QDateEdit, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QSpinBox, QStackedWidget,
                               QTimeEdit, QVBoxLayout, QWidget)


class FilterCard(QFrame):
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)

        self.date_label = QLabel("日期")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())

        self.time_label = QLabel("开始")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(18, 0))

        self.slot_label = QLabel("时段")
        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(1, 6)
        self.slot_spin.setValue(2)

        self.venue_label = QLabel("场地")
        self.venue_spin = QSpinBox()
        self.venue_spin.setRange(1, 9999)
        self.venue_spin.setValue(57)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setObjectName("secondaryAction")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        self.filter_stack = QStackedWidget()
        self.expanded_panel = QWidget()
        self.compact_panel = QWidget()
        self.expanded_layout = QHBoxLayout(self.expanded_panel)
        self.expanded_layout.setContentsMargins(0, 0, 0, 0)
        self.expanded_layout.setSpacing(8)
        self.compact_layout = QGridLayout(self.compact_panel)
        self.compact_layout.setContentsMargins(0, 0, 0, 0)
        self.compact_layout.setHorizontalSpacing(8)
        self.compact_layout.setVerticalSpacing(8)
        self.filter_stack.addWidget(self.expanded_panel)
        self.filter_stack.addWidget(self.compact_panel)
        self.update_layout(compact=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title = QLabel("筛选条件")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        layout.addWidget(self.filter_stack)

    def current_values(self) -> dict[str, object]:
        return {
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "start_time": self.time_edit.time().toString("HH:mm"),
            "slot_count": self.slot_spin.value(),
            "venue_site_id": self.venue_spin.value(),
        }

    def update_layout(self, *, compact: bool) -> None:
        self._clear_layout(self.expanded_layout)
        self._clear_layout(self.compact_layout)
        if compact:
            self.compact_layout.addWidget(self.date_label, 0, 0)
            self.compact_layout.addWidget(self.date_edit, 0, 1)
            self.compact_layout.addWidget(self.time_label, 0, 2)
            self.compact_layout.addWidget(self.time_edit, 0, 3)
            self.compact_layout.addWidget(self.slot_label, 1, 0)
            self.compact_layout.addWidget(self.slot_spin, 1, 1)
            self.compact_layout.addWidget(self.venue_label, 1, 2)
            self.compact_layout.addWidget(self.venue_spin, 1, 3)
            self.compact_layout.addWidget(self.refresh_button, 0, 4, 2, 1)
            self.filter_stack.setCurrentWidget(self.compact_panel)
            return

        self.expanded_layout.addWidget(self.date_label)
        self.expanded_layout.addWidget(self.date_edit)
        self.expanded_layout.addWidget(self.time_label)
        self.expanded_layout.addWidget(self.time_edit)
        self.expanded_layout.addWidget(self.slot_label)
        self.expanded_layout.addWidget(self.slot_spin)
        self.expanded_layout.addWidget(self.venue_label)
        self.expanded_layout.addWidget(self.venue_spin)
        self.expanded_layout.addStretch(1)
        self.expanded_layout.addWidget(self.refresh_button)
        self.filter_stack.setCurrentWidget(self.expanded_panel)

    def set_values(self, *, date: str, start_time: str, slot_count: int, venue_site_id: int) -> None:
        if date:
            parsed = QDate.fromString(date, "yyyy-MM-dd")
            if parsed.isValid():
                self.date_edit.setDate(parsed)
        if start_time:
            parsed_time = QTime.fromString(start_time, "HH:mm")
            if parsed_time.isValid():
                self.time_edit.setTime(parsed_time)
        self.slot_spin.setValue(max(self.slot_spin.minimum(), min(slot_count, self.slot_spin.maximum())))
        self.venue_spin.setValue(venue_site_id)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)
            if widget is not None:
                widget.setParent(None)
