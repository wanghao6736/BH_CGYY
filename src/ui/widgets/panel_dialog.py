"""设置面板：用户配置信息"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QFormLayout, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QVBoxLayout, QWidget)

from src.ui.form_options import (apply_date_to_combo, apply_time_to_combo,
                                 build_date_options, build_time_options,
                                 normalize_time_option, resolve_request_date,
                                 with_any_time_option)
from src.ui.state import BuddyOption, SettingsFormState
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

    saveRequested = Signal()

    _STRATEGY_OPTIONS = [
        ("同一场馆", "same_first_digit"),
        ("同一场地", "same_venue"),
        ("最低价格", "cheapest"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panelDialog", "true")
        self.setWindowTitle("设置")
        self.resize(320, 320)
        self._profile_name = "default"
        self._buddy_options: list[BuddyOption] = []
        self._buddy_supported = False

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
        self.buddy_combo = CustomComboBox(multi_select=True)
        self.buddy_combo.setPlaceholderText("选择同伴")
        self.buddy_combo.setFixedWidth(80)
        self.strategy_combo = CustomComboBox(multi_select=True)
        self.strategy_combo.setPlaceholderText("选择策略")
        self.strategy_combo.setFixedWidth(80)
        self.strategy_combo.setItemsWithData(self._STRATEGY_OPTIONS)

        form_layout.addRow("显示名", self.display_name_input)
        form_layout.addRow("手机号", self.phone_input)

        # 默认参数 - 使用网格布局实现两列
        params_widget = QWidget()
        params_grid = QGridLayout(params_widget)
        params_grid.setContentsMargins(0, 0, 0, 0)
        params_grid.setSpacing(8)

        # 第一行：场地、时段
        site_label = QLabel("🏟️ 场地")
        self.settings_site_input = CustomLineEdit(placeholder="场地ID")
        self.settings_site_input.setFixedWidth(70)
        self.settings_site_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        slot_label = QLabel("🕒 时段")
        self.settings_slot_input = CustomComboBox()
        self.settings_slot_input.addItems([f"{i}段" for i in range(1, 7)])
        self.settings_slot_input.setFixedWidth(80)

        params_grid.addWidget(site_label, 0, 0)
        params_grid.addWidget(self.settings_site_input, 0, 1)
        params_grid.addWidget(slot_label, 0, 2)
        params_grid.addWidget(self.settings_slot_input, 0, 3)

        # 第二行：日期、时间
        date_label = QLabel("🗓️ 日期")
        self.settings_date_input = CustomComboBox()
        self.settings_date_input.addItems(build_date_options())
        self.settings_date_input.setFixedWidth(80)

        time_label = QLabel("⌚️ 时间")
        self.settings_start_input = CustomComboBox()
        self.settings_start_input.addItems(build_time_options(include_any=True))
        apply_time_to_combo(self.settings_start_input, "")
        self.settings_start_input.setFixedWidth(80)

        params_grid.addWidget(date_label, 1, 0)
        params_grid.addWidget(self.settings_date_input, 1, 1)
        params_grid.addWidget(time_label, 1, 2)
        params_grid.addWidget(self.settings_start_input, 1, 3)

        # 第三行：同伴、策略
        buddy_label = QLabel("👥 同伴")
        strategy_label = QLabel("🎯 策略")
        for label in (buddy_label, strategy_label):
            label.setFixedWidth(48)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        params_grid.addWidget(buddy_label, 2, 0)
        params_grid.addWidget(self.buddy_combo, 2, 1)
        params_grid.addWidget(strategy_label, 2, 2)
        params_grid.addWidget(self.strategy_combo, 2, 3)

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
        self.save_settings_button.clicked.connect(self.saveRequested.emit)
        button_layout.addWidget(self.save_settings_button)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)

    def set_target_summary(self, text: str) -> None:
        self.target_summary.setText(text or "未选择目标")

    def set_save_enabled(self, enabled: bool) -> None:
        self.save_settings_button.setEnabled(enabled)

    def set_date_options(self, _options: list[str] | None = None) -> None:
        current_value = resolve_request_date(self.settings_date_input.currentText())
        self.settings_date_input.clear()
        self.settings_date_input.addItems(build_date_options())
        apply_date_to_combo(self.settings_date_input, current_value)

    def set_time_options(self, options: list[str]) -> None:
        current_value = self.settings_start_input.currentText()
        self.settings_start_input.clear()
        self.settings_start_input.addItems(with_any_time_option(options or build_time_options()))
        apply_time_to_combo(self.settings_start_input, current_value)

    def _split_buddy_ids(self, value: str) -> list[str]:
        return [item.strip() for item in (value or "").split(",") if item.strip()]

    def _split_strategy_spec(self, value: str) -> list[str]:
        return [item.strip() for item in (value or "").split(",") if item.strip()]

    def _current_buddy_ids(self) -> list[str]:
        return [str(item) for item in self.buddy_combo.checkedData() if str(item).strip()]

    def _current_strategy_names(self) -> list[str]:
        return [str(item) for item in self.strategy_combo.checkedData() if str(item).strip()]

    def _render_buddy_options(self, selected_ids: list[str]) -> None:
        items = [(item.name or item.id, item.id) for item in self._buddy_options]
        known_ids = {item.id for item in self._buddy_options}
        for buddy_id in selected_ids:
            if buddy_id not in known_ids:
                items.append((f"ID {buddy_id}", buddy_id))
        self.buddy_combo.setItemsWithData(items)
        self.buddy_combo.setCheckedData(selected_ids)
        self.buddy_combo.setPlaceholderText("选择同伴" if self._buddy_supported else "无需同伴")

    def _render_strategy_options(self, selected_names: list[str]) -> None:
        items = list(self._STRATEGY_OPTIONS)
        known_names = {data for _, data in self._STRATEGY_OPTIONS}
        for name in selected_names:
            if name not in known_names:
                items.append((name, name))
        self.strategy_combo.setItemsWithData(items)
        self.strategy_combo.setCheckedData(selected_names)
        self.strategy_combo.setPlaceholderText("选择策略")

    def set_buddy_options(
        self,
        options: list[BuddyOption],
        *,
        buddy_num_min: int = 0,
        buddy_num_max: int = 0,
    ) -> None:
        current_ids = self._current_buddy_ids()
        self._buddy_options = list(options)
        self._buddy_supported = bool(options or buddy_num_min > 0 or buddy_num_max > 0)
        self._render_buddy_options(current_ids)

    def apply_runtime_defaults(
        self,
        *,
        phone: str = "",
        buddy_ids: list[str] | None = None,
    ) -> None:
        if phone and not self.phone_input.text().strip():
            self.phone_input.setText(phone)
        if buddy_ids and not self._current_buddy_ids():
            self._render_buddy_options([str(item) for item in buddy_ids if str(item).strip()])

    def apply_state(self, state: SettingsFormState) -> None:
        self._profile_name = state.profile_name
        self.display_name_input.setText(state.display_name)
        self.phone_input.setText(state.phone)
        self._render_buddy_options(self._split_buddy_ids(state.buddy_ids))
        self._render_strategy_options(self._split_strategy_spec(state.selection_strategy))
        self.settings_site_input.setText(str(state.venue_site_id))
        self.settings_slot_input.setCurrentIndex(max(0, min(state.slot_count - 1, 5)))
        apply_date_to_combo(self.settings_date_input, state.default_search_date)
        apply_time_to_combo(self.settings_start_input, state.start_time)

    def collect_state(self, *, profile_name: str | None = None) -> SettingsFormState:
        active_profile = profile_name or self._profile_name or "default"
        try:
            venue_site_id = int(self.settings_site_input.text().strip() or "57")
        except ValueError:
            venue_site_id = 57

        return SettingsFormState(
            profile_name=active_profile,
            display_name=self.display_name_input.text().strip(),
            phone=self.phone_input.text().strip(),
            buddy_ids=",".join(self._current_buddy_ids()),
            selection_strategy=",".join(self._current_strategy_names()),
            venue_site_id=venue_site_id,
            default_search_date=resolve_request_date(self.settings_date_input.currentText()),
            start_time=normalize_time_option(self.settings_start_input.currentText()),
            slot_count=self.settings_slot_input.currentIndex() + 1,
        )
