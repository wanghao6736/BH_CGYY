from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QFrame, QLabel, QVBoxLayout

from src.ui.widgets.custom_combo import CustomComboBox


# 统一的列宽配置
LABEL_WIDTH = 56
FIELD_WIDTH = 90


def resolve_request_date(date_text: str, today: QDate) -> str:
    """将日期下拉文本解析为 yyyy-MM-dd。"""
    if date_text in ("今天", "明天"):
        offset = 0 if date_text == "今天" else 1
        return today.addDays(offset).toString("yyyy-MM-dd")

    month, day = map(int, date_text.split("-"))
    candidate = QDate(today.year(), month, day)
    if candidate.isValid() and candidate < today:
        candidate = candidate.addYears(1)
    return candidate.toString("yyyy-MM-dd") if candidate.isValid() else today.toString("yyyy-MM-dd")


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
        self.time_combo.setCurrentIndex(20)

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

        self._venue_data: dict[str, dict] = {}
        self._init_venue_data()
        self._sync_column_text_widths()

        # 目标摘要
        self.target_summary = QLabel("未选择目标")
        self.target_summary.setProperty("summary", "true")

        # 使用网格布局实现严格对齐
        grid = QGridLayout()
        grid.setSpacing(4)  # 行间距、列间距
        grid.setContentsMargins(0, 0, 0, 0)

        # 第一行：日期、时间、时长
        row1_labels = ["日期", "时间", "时长"]
        row1_combos = [self.date_combo, self.time_combo, self.slot_combo]

        for col, (label_text, combo) in enumerate(zip(row1_labels, row1_combos)):
            label = QLabel(label_text)
            label.setFixedWidth(LABEL_WIDTH)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            label.setProperty("role", "label")
            grid.addWidget(label, 0, col * 2)
            grid.addWidget(combo, 0, col * 2 + 1)

        # 第二行：校区、场馆、场地
        row2_labels = ["校区", "场馆", "场地"]
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
        for combo in [self.date_combo, self.time_combo, self.slot_combo,
                      self.campus_combo, self.venue_combo, self.court_combo]:
            combo.currentIndexChanged.connect(lambda _: self.paramsChanged.emit())

        self.campus_combo.currentIndexChanged.connect(self._on_campus_changed)
        self.venue_combo.currentIndexChanged.connect(self._on_venue_changed)

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
        self.date_combo.addItems(dates)

    def _init_times(self) -> None:
        """初始化时间选项（08:00-22:00，步进30分钟）"""
        times = []
        hour = 8
        while hour < 22:
            times.append(f"{hour:02d}:00")
            times.append(f"{hour:02d}:30")
            hour += 1
        self.time_combo.addItems(times)

    def _init_venue_data(self) -> None:
        """初始化场地数据"""
        self._venue_data = {
            "学院路": {
                "羽毛球馆": {f"{i}号场": 50 + i for i in range(1, 9)},
                "乒乓球馆": {f"{i}号台": 60 + i for i in range(1, 5)},
            },
            "沙河": {
                "羽毛球馆": {f"{i}号场": 70 + i for i in range(1, 7)},
                "网球馆": {f"{i}号场": 80 + i for i in range(1, 5)},
            },
        }
        self._refresh_campus_list()

    def _refresh_campus_list(self) -> None:
        """刷新校区列表"""
        self.campus_combo.clear()
        campuses = list(self._venue_data.keys())
        self.campus_combo.addItems(campuses)
        if campuses:
            self._on_campus_changed(0)

    def _on_campus_changed(self, index: int) -> None:
        """校区切换时更新场馆列表"""
        campus = self.campus_combo.currentText()
        if campus not in self._venue_data:
            return
        venues = list(self._venue_data[campus].keys())
        self.venue_combo.clear()
        self.venue_combo.addItems(venues)
        if venues:
            self._on_venue_changed(0)
        self._sync_column_text_widths()

    def _on_venue_changed(self, index: int) -> None:
        """场馆切换时更新场地列表"""
        campus = self.campus_combo.currentText()
        venue = self.venue_combo.currentText()
        if campus not in self._venue_data or venue not in self._venue_data[campus]:
            return
        courts = list(self._venue_data[campus][venue].keys())
        self.court_combo.clear()
        self.court_combo.addItems(courts)
        self._sync_column_text_widths()

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

    def set_venue_data(self, data: dict) -> None:
        """设置场地数据"""
        self._venue_data = data
        self._refresh_campus_list()

    def venue_site_id(self) -> int:
        """获取当前选中的场地ID"""
        campus = self.campus_combo.currentText()
        venue = self.venue_combo.currentText()
        court = self.court_combo.currentText()
        try:
            return self._venue_data[campus][venue][court]
        except KeyError:
            return 57

    def current_request_values(self) -> dict:
        """获取当前请求参数"""
        date = resolve_request_date(self.date_combo.currentText(), QDate.currentDate())
        return {
            "date": date,
            "start_time": self.time_combo.currentText(),
            "slot_count": self.slot_combo.currentIndex() + 1,
            "venue_site_id": self.venue_site_id(),
        }

    def set_target_summary(self, text: str) -> None:
        self.target_summary.setText(text or "未选择目标")

    def set_values(self, *, date: str, start_time: str, slot_count: int, venue_site_id: int) -> None:
        """设置参数值"""
        if date:
            parsed = QDate.fromString(date, "yyyy-MM-dd")
            if parsed.isValid():
                today = QDate.currentDate()
                days_diff = today.daysTo(parsed)
                if days_diff == 0:
                    self.date_combo.setCurrentIndex(0)
                elif days_diff == 1:
                    self.date_combo.setCurrentIndex(1)
                else:
                    date_text = parsed.toString("MM-dd")
                    idx = self.date_combo.findText(date_text)
                    if idx >= 0:
                        self.date_combo.setCurrentIndex(idx)

        time_idx = self.time_combo.findText(start_time)
        if time_idx >= 0:
            self.time_combo.setCurrentIndex(time_idx)

        self.slot_combo.setCurrentIndex(max(0, min(slot_count - 1, 5)))

        for campus, venues in self._venue_data.items():
            for venue, courts in venues.items():
                for court, vid in courts.items():
                    if vid == venue_site_id:
                        campus_idx = self.campus_combo.findText(campus)
                        if campus_idx >= 0:
                            self.campus_combo.setCurrentIndex(campus_idx)
                        venue_idx = self.venue_combo.findText(venue)
                        if venue_idx >= 0:
                            self.venue_combo.setCurrentIndex(venue_idx)
                        court_idx = self.court_combo.findText(court)
                        if court_idx >= 0:
                            self.court_combo.setCurrentIndex(court_idx)
                        return
