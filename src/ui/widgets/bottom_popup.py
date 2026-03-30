from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget


class BottomPopup(QWidget):
    """底部弹层基类，统一处理定位、拖动和点击外部关闭。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._app_filter_installed = False
        self._visible = False
        self._drag_pos: Optional[QPoint] = None

    def show_at_bottom(self) -> None:
        """在父窗口下方居中显示，空间不足时回退到上方。"""
        self.on_before_show_at_bottom()
        parent = self.parent()
        if parent is None:
            return

        parent_rect = parent.frameGeometry()
        target_width = max(self.sizeHint().width(), parent_rect.width() - 16)
        self.setFixedWidth(target_width)
        self.adjustSize()
        self._position_relative_to_parent()
        self._install_app_event_filter()
        self.show()
        self._visible = True
        QTimer.singleShot(0, self._reposition_after_show)

    def on_before_show_at_bottom(self) -> None:
        """显示前的扩展钩子。"""

    def on_before_hide(self) -> None:
        """隐藏前的扩展钩子。"""

    def has_active_child_popup(self) -> bool:
        """是否存在阻止外部点击关闭的子弹层。"""
        return False

    def can_start_drag(self, local_pos: QPoint) -> bool:
        """是否允许从当前位置开始拖动。"""
        return True

    def _position_relative_to_parent(self) -> None:
        parent = self.parent()
        if parent is None:
            return

        parent_rect = parent.frameGeometry()
        popup_rect = self.frameGeometry()
        popup_width = popup_rect.width() or self.width()
        popup_height = popup_rect.height() or self.height()

        x = parent_rect.center().x() - popup_width // 2
        y = parent_rect.bottom() + 8

        screen = parent.screen()
        if screen is not None:
            screen_rect = screen.availableGeometry()
            if y + popup_height > screen_rect.bottom():
                y = parent_rect.top() - popup_height - 8
            if x + popup_width > screen_rect.right():
                x = screen_rect.right() - popup_width
            if x < screen_rect.left():
                x = screen_rect.left()

        self.move(x, y)

    def _reposition_after_show(self) -> None:
        if not self.isVisible():
            return
        self.adjustSize()
        self._position_relative_to_parent()

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
        if not self._visible:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            if hasattr(event, "globalPosition"):
                global_pos = event.globalPosition().toPoint()
            elif hasattr(event, "globalPos"):
                global_pos = event.globalPos()
            else:
                return super().eventFilter(obj, event)

            popup_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
            if not popup_rect.contains(global_pos) and not self.has_active_child_popup():
                self.hide()
                self._visible = False
                return False

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.can_start_drag(
            event.position().toPoint()
        ):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event) -> None:
        self._visible = False
        self._remove_app_event_filter()
        self.on_before_hide()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        self._visible = False
        self._remove_app_event_filter()
        self.on_before_hide()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
