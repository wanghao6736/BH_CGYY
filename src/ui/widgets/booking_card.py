from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from src.ui.form_options import (apply_date_to_combo, apply_time_to_combo,
                                 build_date_options, build_time_options,
                                 normalize_time_option, resolve_request_date,
                                 with_any_time_option)
from src.ui.state import BookingFormState, VenueCatalogState
from src.ui.widgets.custom_combo import CustomComboBox

# 统一的列宽配置
LABEL_WIDTH = 56
FIELD_WIDTH = 120


class BookingCard(QFrame):
    """参数区：2行3列布局，使用网格对齐"""

    paramsChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("bookingCard", "true")

        # 第一行参数
        self.date_combo = CustomComboBox()
        self._init_dates()

        self.time_combo = CustomComboBox()
        self._init_times()
        self.time_combo.setCurrentIndex(21)

        self.slot_combo = CustomComboBox()
        self.slot_combo.addItems([f"{i}段" for i in range(1, 7)])
        self.slot_combo.setCurrentIndex(1)

        # 第二行参数
        self.campus_combo = CustomComboBox()
        self.venue_combo = CustomComboBox()
        self.court_combo = CustomComboBox()

        for combo in [
            self.date_combo,
            self.time_combo,
            self.slot_combo,
            self.campus_combo,
            self.venue_combo,
            self.court_combo,
        ]:
            combo.setFixedWidth(FIELD_WIDTH)

        self._state = BookingFormState(
            date=resolve_request_date(self.date_combo.currentText(), QDate.currentDate()),
            start_time=self.time_combo.currentText(),
            slot_count=self.slot_combo.currentIndex() + 1,
            venue_site_id=57,
        )
        self._venue_data: dict[str, dict] = {}
        self._sync_column_text_widths()

        # 目标摘要
        self.target_summary = QLabel("未选择目标")
        self.target_summary.setProperty("summary", "true")
        self.target_summary.setWordWrap(True)

        # 使用网格布局实现严格对齐
        grid = QGridLayout()
        grid.setSpacing(4)  # 行间距、列间距
        grid.setContentsMargins(0, 0, 0, 0)

        # 第一行：日期、时间、时长
        row1_labels = ["🗓️ 日期", "🕐 时间", "🔢 时长"]
        row1_combos = [self.date_combo, self.time_combo, self.slot_combo]

        for col, (label_text, combo) in enumerate(zip(row1_labels, row1_combos)):
            label = QLabel(label_text)
            label.setFixedWidth(LABEL_WIDTH)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            label.setProperty("role", "label")
            grid.addWidget(label, 0, col * 2)
            grid.addWidget(combo, 0, col * 2 + 1)

        # 第二行：校区、场馆、场地
        row2_labels = ["🏫 校区", "🏟️ 场馆", "🏸 场地"]
        row2_combos = [self.campus_combo, self.venue_combo, self.court_combo]

        for col, (label_text, combo) in enumerate(zip(row2_labels, row2_combos)):
            label = QLabel(label_text)
            label.setFixedWidth(LABEL_WIDTH)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            label.setProperty("role", "label")
            grid.addWidget(label, 1, col * 2)
            grid.addWidget(combo, 1, col * 2 + 1)

        for col in range(3):
            grid.setColumnMinimumWidth(col * 2, LABEL_WIDTH)
            grid.setColumnMinimumWidth(col * 2 + 1, FIELD_WIDTH)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addLayout(grid)
        layout.addWidget(self.target_summary)

        # 连接信号
        self.date_combo.currentIndexChanged.connect(self._emit_params_changed)
        self.time_combo.currentIndexChanged.connect(self._emit_params_changed)
        self.slot_combo.currentIndexChanged.connect(self._emit_params_changed)
        self.court_combo.currentIndexChanged.connect(self._emit_params_changed)
        self.campus_combo.currentIndexChanged.connect(self._on_campus_changed)
        self.venue_combo.currentIndexChanged.connect(self._on_venue_changed)

    def _init_dates(self) -> None:
        """初始化日期选项（未来7天）"""
        self.date_combo.addItems(build_date_options())

    def _init_times(self) -> None:
        """初始化时间选项（08:00-22:00，步进30分钟）"""
        self.time_combo.addItems(build_time_options(include_any=True))

    def _refresh_campus_list(self) -> None:
        """刷新校区列表"""
        self.campus_combo.clear()
        campuses = list(self._venue_data.keys())
        self.campus_combo.addItems(campuses)
        if campuses:
            self._on_campus_changed(0)
        else:
            self.venue_combo.clear()
            self.court_combo.clear()
        self._sync_column_text_widths()

    def _on_campus_changed(self, index: int) -> None:
        """校区切换时更新场馆列表"""
        campus = self.campus_combo.currentText()
        if campus not in self._venue_data:
            self.venue_combo.clear()
            self.court_combo.clear()
            self._emit_params_changed()
            return
        venues = list(self._venue_data[campus].keys())
        self.venue_combo.clear()
        self.venue_combo.addItems(venues)
        if venues:
            self._on_venue_changed(0)
        self._sync_column_text_widths()
        self._emit_params_changed()

    def _on_venue_changed(self, index: int) -> None:
        """场馆切换时更新场地列表"""
        campus = self.campus_combo.currentText()
        venue = self.venue_combo.currentText()
        if campus not in self._venue_data or venue not in self._venue_data[campus]:
            self.court_combo.clear()
            self._emit_params_changed()
            return
        courts = list(self._venue_data[campus][venue].keys())
        self.court_combo.clear()
        self.court_combo.addItems(courts)
        self._sync_column_text_widths()
        self._emit_params_changed()

    def _sync_column_text_widths(self) -> None:
        """同步三列下拉的最小文本宽度，保证同列视觉左对齐。"""
        col0 = max(self.date_combo.maxItemTextWidth(), self.campus_combo.maxItemTextWidth())
        col1 = max(self.time_combo.maxItemTextWidth(), self.venue_combo.maxItemTextWidth())
        col2 = max(self.slot_combo.maxItemTextWidth(), self.court_combo.maxItemTextWidth())
        for combo in (self.date_combo, self.campus_combo):
            combo.setDisplayMinTextWidth(col0)
        for combo in (self.time_combo, self.venue_combo):
            combo.setDisplayMinTextWidth(col1)
        for combo in (self.slot_combo, self.court_combo):
            combo.setDisplayMinTextWidth(col2)

    def _emit_params_changed(self, *_args) -> None:
        self._sync_state_from_controls()
        self.paramsChanged.emit()

    def _selected_venue_site_id(self) -> int | None:
        campus = self.campus_combo.currentText()
        venue = self.venue_combo.currentText()
        court = self.court_combo.currentText()
        try:
            return self._venue_data[campus][venue][court]
        except KeyError:
            return None

    def _sync_state_from_controls(self) -> None:
        self._state = BookingFormState(
            date=resolve_request_date(self.date_combo.currentText(), QDate.currentDate()),
            start_time=normalize_time_option(self.time_combo.currentText()),
            slot_count=self.slot_combo.currentIndex() + 1,
            venue_site_id=self._selected_venue_site_id() or self._state.venue_site_id,
        )

    def _select_venue_site_id(self, venue_site_id: int) -> bool:
        for campus, venues in self._venue_data.items():
            for venue, courts in venues.items():
                for court, current_site_id in courts.items():
                    if current_site_id != venue_site_id:
                        continue
                    campus_idx = self.campus_combo.findText(campus)
                    if campus_idx >= 0:
                        self.campus_combo.setCurrentIndex(campus_idx)
                    venue_idx = self.venue_combo.findText(venue)
                    if venue_idx >= 0:
                        self.venue_combo.setCurrentIndex(venue_idx)
                    court_idx = self.court_combo.findText(court)
                    if court_idx >= 0:
                        self.court_combo.setCurrentIndex(court_idx)
                    return True
        return False

    def set_date_options(self, _options: list[str] | None = None) -> None:
        current_value = self._state.date or resolve_request_date(self.date_combo.currentText(), QDate.currentDate())
        self.date_combo.clear()
        self.date_combo.addItems(build_date_options())
        apply_date_to_combo(self.date_combo, current_value)
        self._sync_column_text_widths()
        self._sync_state_from_controls()

    def set_time_options(self, options: list[str]) -> None:
        current_value = self._state.start_time or self.time_combo.currentText()
        self.time_combo.clear()
        self.time_combo.addItems(with_any_time_option(options or build_time_options()))
        apply_time_to_combo(self.time_combo, current_value)
        self._sync_column_text_widths()
        self._sync_state_from_controls()

    def set_venue_data(self, catalog_state: VenueCatalogState) -> None:
        """设置场地目录数据。"""
        preferred_site_id = self._state.venue_site_id
        self._venue_data = {}
        for item in catalog_state.items:
            self._venue_data.setdefault(item.campus_name, {}).setdefault(item.venue_name, {})[
                item.site_name
            ] = item.venue_site_id
        self._refresh_campus_list()
        self._select_venue_site_id(preferred_site_id)
        self._sync_column_text_widths()
        self._sync_state_from_controls()

    def set_target_summary(self, text: str) -> None:
        self.target_summary.setText(text or "未选择目标")

    def collect_state(self) -> BookingFormState:
        self._sync_state_from_controls()
        return BookingFormState(
            date=self._state.date,
            start_time=self._state.start_time,
            slot_count=self._state.slot_count,
            venue_site_id=self._state.venue_site_id,
        )

    def apply_state(self, state: BookingFormState) -> None:
        self._state = BookingFormState(
            date=state.date,
            start_time=state.start_time,
            slot_count=state.slot_count,
            venue_site_id=state.venue_site_id,
        )
        apply_date_to_combo(self.date_combo, state.date)
        apply_time_to_combo(self.time_combo, state.start_time)
        self.slot_combo.setCurrentIndex(max(0, min(state.slot_count - 1, 5)))
        self._select_venue_site_id(state.venue_site_id)
        self._sync_column_text_widths()
        self._sync_state_from_controls()
