"""轮询弹窗：底部弹出，非模态，点击外部关闭"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
)

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


class PollDialog(QWidget):
    """轮询参数弹窗 - 底部弹出，非模态，点击外部关闭"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("pollDialog", "true")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.body = QFrame(self)
        self.body.setProperty("pollDialogBody", "true")

        # 开始时间
        self.start_label = QLabel("⏰ 开始")
        self.start_time_combo = CustomComboBox()
        self.start_time_combo.setFixedWidth(90)
        self._init_start_times()

        # 间隔
        self.interval_label = QLabel("↻ 间隔")
        self.interval_combo = CustomComboBox()
        self.interval_combo.setFixedWidth(90)
        self.interval_combo.addItems([item[0] for item in POLL_INTERVALS])

        # 开始按钮
        self.start_button = QPushButton("▶ 开始")
        self.start_button.setObjectName("startButton")
        self.start_button.setFixedHeight(24)

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

        self._app_filter_installed = False
        self._visible = False

    def _init_start_times(self) -> None:
        """初始化开始时间选项"""
        now = datetime.now()
        rounded = round_up_to_5_minutes(now)
        times = []
        for i in range(24):
            t = rounded + timedelta(minutes=i * 5)
            times.append(t.strftime("%H:%M"))
        self.start_time_combo.addItems(times)

    def get_start_time(self) -> str:
        return self.start_time_combo.currentText()

    def get_interval_seconds(self) -> int:
        idx = self.interval_combo.currentIndex()
        if 0 <= idx < len(POLL_INTERVALS):
            return POLL_INTERVALS[idx][1]
        return 30

    def show_at_bottom(self) -> None:
        """在父窗口下方居中显示"""
        self.start_time_combo.clear()
        self._init_start_times()

        parent = self.parent()
        if parent is None:
            return

        self.adjustSize()
        parent_rect = parent.frameGeometry()
        target_width = max(self.sizeHint().width(), parent_rect.width() - 16)
        self.setFixedWidth(target_width)

        # 默认显示在父窗口下方，有8px间距
        x = parent_rect.center().x() - self.width() // 2
        y = parent_rect.bottom() + 8

        # 屏幕空间不足时回退到父窗口上方
        screen = parent.screen()
        if screen is not None:
            screen_rect = screen.availableGeometry()
            if y + self.height() > screen_rect.bottom():
                y = parent_rect.top() - self.height() - 8
            if x + self.width() > screen_rect.right():
                x = screen_rect.right() - self.width()
            if x < screen_rect.left():
                x = screen_rect.left()

        self.move(x, y)
        self._install_app_event_filter()
        self.show()
        self._visible = True

    def _install_app_event_filter(self) -> None:
        if self._app_filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._app_filter_installed = True

    def _remove_app_event_filter(self) -> None:
        if not self._app_filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._app_filter_installed = False

    def eventFilter(self, obj, event) -> bool:
        """事件过滤器：检测点击外部关闭"""
        if not self._visible:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            # 获取全局坐标
            if hasattr(event, "globalPosition"):
                global_pos = event.globalPosition().toPoint()
            elif hasattr(event, "globalPos"):
                global_pos = event.globalPos()
            else:
                return super().eventFilter(obj, event)

            # 使用全局坐标计算 dialog 矩形
            dialog_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())

            # 检查是否有子 popup 打开
            has_active_popup = (
                self.start_time_combo.isPopupVisible()
                or self.interval_combo.isPopupVisible()
            )

            # 点击在 dialog 外，且没有子 popup 打开 → 关闭 dialog
            if not dialog_rect.contains(global_pos) and not has_active_popup:
                self.hide()
                self._visible = False
                return False

        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        """关闭事件"""
        self._visible = False
        self._remove_app_event_filter()
        self.start_time_combo.hidePopup()
        self.interval_combo.hidePopup()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        self._visible = False
        self._remove_app_event_filter()
        self.start_time_combo.hidePopup()
        self.interval_combo.hidePopup()
        super().hideEvent(event)