from __future__ import annotations

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import (QDateEdit, QDialog, QFormLayout, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTabWidget,
                               QTimeEdit, QVBoxLayout, QWidget)


class PanelDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panelDialog", "true")
        self.setWindowTitle("设置")
        self.resize(360, 420)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        target_tab = QWidget()
        target_layout = QVBoxLayout(target_tab)
        self.target_summary = QLabel("未选择目标")
        self.target_summary.setWordWrap(True)
        target_layout.addWidget(self.target_summary)
        target_layout.addStretch(1)
        self.tabs.addTab(target_tab, "目标")

        settings_tab = QWidget()
        settings_layout = QFormLayout(settings_tab)
        self.display_name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.buddy_input = QLineEdit()
        self.settings_site_input = QSpinBox()
        self.settings_site_input.setRange(1, 9999)
        self.settings_site_input.setValue(57)
        self.settings_date_edit = QDateEdit()
        self.settings_date_edit.setCalendarPopup(True)
        self.settings_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.settings_date_edit.setDate(QDate.currentDate())
        self.settings_start_time_edit = QTimeEdit()
        self.settings_start_time_edit.setDisplayFormat("HH:mm")
        self.settings_start_time_edit.setTime(QTime(18, 0))
        self.settings_slot_input = QSpinBox()
        self.settings_slot_input.setRange(1, 6)
        self.settings_slot_input.setValue(2)
        self.save_settings_button = QPushButton("保存配置")
        self.save_settings_button.setProperty("variant", "primary")
        settings_layout.addRow("显示名", self.display_name_input)
        settings_layout.addRow("手机号", self.phone_input)
        settings_layout.addRow("同伴 IDs", self.buddy_input)
        settings_layout.addRow("默认场地", self.settings_site_input)
        settings_layout.addRow("默认日期", self.settings_date_edit)
        settings_layout.addRow("默认开始", self.settings_start_time_edit)
        settings_layout.addRow("默认时段", self.settings_slot_input)
        settings_layout.addRow(self.save_settings_button)
        self.tabs.addTab(settings_tab, "设置")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.tabs)