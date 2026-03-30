"""设置面板：用户配置信息"""
from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.widgets.custom_combo import CustomComboBox
from src.ui.widgets.custom_lineedit import CustomLineEdit


class PanelDialog(QDialog):
    """设置面板 - 用户配置信息

    布局结构：
    ┌─────────────────────────────────┐
    │ 目标: [选择摘要]                 │
    ├─────────────────────────────────┤
    │ 显示名  [___________________]   │
    │ 手机号  [___________________]   │
    │ 同伴ID  [___________________]   │
    │ 默认场地 [_____] 默认时段 [下拉] │
    │ 默认日期 [下拉] 开始时间 [下拉]  │
    │                                 │
    │        [ 保存配置 ]              │
    └─────────────────────────────────┘
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panelDialog", "true")
        self.setWindowTitle("设置")
        self.resize(320, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 目标摘要
        self.target_summary = QLabel("未选择目标")
        self.target_summary.setProperty("summary", "true")
        self.target_summary.setWordWrap(True)
        layout.addWidget(self.target_summary)

        # 分隔线
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: #E5E7EB;")
        layout.addWidget(separator)

        # 表单区域
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # 基本信息
        self.display_name_input = CustomLineEdit(placeholder="显示名称")
        self.phone_input = CustomLineEdit(placeholder="手机号码")
        self.buddy_input = CustomLineEdit(placeholder="同伴ID，逗号分隔")

        form_layout.addRow("显示名", self.display_name_input)
        form_layout.addRow("手机号", self.phone_input)
        form_layout.addRow("同伴ID", self.buddy_input)

        # 默认参数 - 使用网格布局实现两列
        params_widget = QWidget()
        params_grid = QGridLayout(params_widget)
        params_grid.setContentsMargins(0, 0, 0, 0)
        params_grid.setSpacing(8)

        # 第一行：场地、时段
        site_label = QLabel("场地")
        self.settings_site_input = CustomLineEdit(placeholder="场地ID")
        self.settings_site_input.setFixedWidth(70)

        slot_label = QLabel("时段")
        self.settings_slot_input = CustomComboBox()
        self.settings_slot_input.addItems([f"{i}段" for i in range(1, 7)])
        self.settings_slot_input.setFixedWidth(80)

        params_grid.addWidget(site_label, 0, 0)
        params_grid.addWidget(self.settings_site_input, 0, 1)
        params_grid.addWidget(slot_label, 0, 2)
        params_grid.addWidget(self.settings_slot_input, 0, 3)

        # 第二行：日期、时间
        date_label = QLabel("日期")
        self.settings_date_input = CustomComboBox()
        self._init_dates()
        self.settings_date_input.setFixedWidth(80)

        time_label = QLabel("时间")
        self.settings_start_input = CustomComboBox()
        self._init_times()
        self.settings_start_input.setFixedWidth(80)

        params_grid.addWidget(date_label, 1, 0)
        params_grid.addWidget(self.settings_date_input, 1, 1)
        params_grid.addWidget(time_label, 1, 2)
        params_grid.addWidget(self.settings_start_input, 1, 3)

        params_grid.setColumnStretch(1, 1)
        params_grid.setColumnStretch(3, 1)

        form_layout.addRow(params_widget)
        layout.addWidget(form_widget)

        # 弹性空间
        layout.addStretch(1)

        # 保存按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.save_settings_button = QPushButton("保存配置")
        self.save_settings_button.setProperty("variant", "primary")
        self.save_settings_button.setFixedWidth(120)
        button_layout.addWidget(self.save_settings_button)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)

    def _init_dates(self) -> None:
        """初始化日期选项（未来7天）"""
        today = QDate.currentDate()
        dates = []
        for i in range(7):
            d = today.addDays(i)
            if i == 0:
                dates.append("今天")
            elif i == 1:
                dates.append("明天")
            else:
                dates.append(d.toString("MM-dd"))
        self.settings_date_input.addItems(dates)

    def _init_times(self) -> None:
        """初始化时间选项（08:00-22:00，步进30分钟）"""
        times = []
        hour = 8
        while hour < 22:
            times.append(f"{hour:02d}:00")
            times.append(f"{hour:02d}:30")
            hour += 1
        self.settings_start_input.addItems(times)
        # 默认选择 18:00
        self.settings_start_input.setCurrentIndex(20)