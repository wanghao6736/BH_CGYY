"""详情热力图面板：底部弹出，非模态，点击外部关闭，支持拖动"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.ui.widgets.heatmap_widget import HeatmapWidget

if TYPE_CHECKING:
    pass


class BoardPanel(QWidget):
    """详情热力图面板 - 底部弹出，非模态，点击外部关闭，支持拖动

    布局结构:
    ┌─────────────────────────────────────────┐
    │ 时段详情              最后同步: 10:30   │
    ├─────────────────────────────────────────┤
    │ [HeatmapWidget - 热力图网格]            │
    └─────────────────────────────────────────┘
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("boardPanel", "true")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # 内部容器（用于圆角边框）
        self.body = QFrame(self)
        self.body.setProperty("boardPanelBody", "true")

        # 标题栏
        self.title_label = QLabel("时段详情")
        self.title_label.setProperty("role", "subtitle")

        self.sync_label = QLabel("未同步")
        self.sync_label.setProperty("role", "muted")

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.sync_label)

        # 热力图组件
        self.heatmap = HeatmapWidget()

        # 选择摘要
        self.selection_summary = QLabel("点击单元格选择时段")
        self.selection_summary.setProperty("summary", "true")

        # 内容布局
        content_layout = QVBoxLayout(self.body)
        content_layout.setContentsMargins(12, 10, 12, 10)
        content_layout.setSpacing(8)
        content_layout.addLayout(title_layout)
        content_layout.addWidget(self.heatmap)
        content_layout.addWidget(self.selection_summary)

        # 外层布局
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.body)

        self._app_filter_installed = False
        self._visible = False
        
        # 拖动支持
        self._drag_pos: Optional[QPoint] = None

    def set_sync_text(self, text: str) -> None:
        """设置同步时间文本"""
        self.sync_label.setText(text or "未同步")

    def set_selection_summary(self, text: str) -> None:
        """设置选择摘要文本"""
        self.selection_summary.setText(text or "点击单元格选择时段")

    def show_at_bottom(self) -> None:
        """在父窗口下方居中显示"""
        parent = self.parent()
        if parent is None:
            return

        self.adjustSize()
        parent_rect = parent.frameGeometry()

        # 计算目标宽度：至少与父窗口同宽（减去边距）
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
        """安装应用级事件过滤器"""
        if self._app_filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._app_filter_installed = True

    def _remove_app_event_filter(self) -> None:
        """移除应用级事件过滤器"""
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

            # 使用全局坐标计算面板矩形
            panel_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())

            # 点击在面板外部 → 关闭面板
            if not panel_rect.contains(global_pos):
                self.hide()
                self._visible = False
                return False

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """鼠标按下：记录拖动起始位置"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 只允许在标题栏区域拖动
            title_rect = QRect(0, 0, self.width(), 40)
            if title_rect.contains(event.position().toPoint()):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """鼠标移动：拖动窗口"""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """鼠标释放：结束拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event) -> None:
        """关闭事件"""
        self._visible = False
        self._remove_app_event_filter()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        """隐藏事件"""
        self._visible = False
        self._remove_app_event_filter()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        """显示事件"""
        super().showEvent(event)
        self.adjustSize()