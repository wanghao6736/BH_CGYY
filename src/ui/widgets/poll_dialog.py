"""轮询弹窗：底部弹出，非模态，点击外部关闭，支持拖动"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.ui.state import PollingConfigState
from src.ui.widgets.bottom_popup import BottomPopup
from src.ui.widgets.custom_combo import CustomComboBox

POLL_INTERVALS = [
    ("10秒", 10),
    ("30秒", 30),
    ("1分钟", 60),
    ("5分钟", 300),
    ("10分钟", 600),
    ("30分钟", 1800),
    ("1小时", 3600),
]


def round_up_to_5_minutes(dt: datetime) -> datetime:
    """向上取整到5分钟"""
    remainder = dt.minute % 5
    delta = 0 if remainder == 0 else 5 - remainder
    rounded = dt + timedelta(minutes=delta)
    return rounded.replace(second=0, microsecond=0)


class PollDialog(BottomPopup):
    """轮询参数弹窗 - 底部弹出，非模态，点击外部关闭，支持拖动"""

    startRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("pollDialog", "true")

        self.body = QFrame(self)
        self.body.setProperty("pollDialogBody", "true")

        # 开始时间
        self.start_label = QLabel("⏰ 开始")
        self.start_time_combo = CustomComboBox()
        self.start_time_combo.setFixedWidth(90)
        self._init_start_times()

        # 间隔
        self.interval_label = QLabel("⏱️ 间隔")
        self.interval_combo = CustomComboBox()
        self.interval_combo.setFixedWidth(90)
        self.interval_combo.addItems([item[0] for item in POLL_INTERVALS])

        # 开始按钮
        self.start_button = QPushButton("🚀 开始")
        self.start_button.setObjectName("startButton")
        self.start_button.setFixedHeight(24)
        self.start_button.clicked.connect(self.startRequested.emit)

        # 布局：外层透明容器 + 内层圆角面板（QSS 控制）
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.body)

        content_layout = QHBoxLayout(self.body)
        content_layout.setContentsMargins(16, 10, 16, 10)
        content_layout.setSpacing(10)
        content_layout.addWidget(self.start_label)
        content_layout.addWidget(self.start_time_combo)
        content_layout.addWidget(self.interval_label)
        content_layout.addWidget(self.interval_combo)
        content_layout.addSpacing(8)
        content_layout.addWidget(self.start_button)

        self.adjustSize()

    def _init_start_times(self) -> None:
        """初始化开始时间选项"""
        now = datetime.now()
        rounded = round_up_to_5_minutes(now)
        times = []
        for i in range(24):
            t = rounded + timedelta(minutes=i * 5)
            times.append(t.strftime("%H:%M"))
        self.start_time_combo.addItems(times)

    def collect_config(self) -> PollingConfigState:
        idx = self.interval_combo.currentIndex()
        interval_sec = POLL_INTERVALS[idx][1] if 0 <= idx < len(POLL_INTERVALS) else 30
        return PollingConfigState(
            start_time=self.start_time_combo.currentText(),
            interval_sec=interval_sec,
        )

    def apply_config(self, state: PollingConfigState) -> None:
        start_idx = self.start_time_combo.findText(state.start_time)
        if start_idx >= 0:
            self.start_time_combo.setCurrentIndex(start_idx)

        interval_idx = next(
            (index for index, (_label, seconds) in enumerate(POLL_INTERVALS) if seconds == state.interval_sec),
            -1,
        )
        if interval_idx >= 0:
            self.interval_combo.setCurrentIndex(interval_idx)

    def on_before_show_at_bottom(self) -> None:
        current_config = self.collect_config()
        self.start_time_combo.clear()
        self._init_start_times()
        self.apply_config(current_config)

    def has_active_child_popup(self) -> bool:
        return self.start_time_combo.isPopupVisible() or self.interval_combo.isPopupVisible()

    def on_before_hide(self) -> None:
        self.start_time_combo.hidePopup()
        self.interval_combo.hidePopup()
