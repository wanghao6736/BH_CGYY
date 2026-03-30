"""自定义下拉选择控件，使用QToolButton + PopupList实现"""
from __future__ import annotations

import weakref
from typing import Any

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QSizePolicy,
                               QToolButton)

from src.ui.widgets.popup_list import PopupList


class CustomComboBox(QFrame):
    """下拉选择控件 - 单一状态源设计"""

    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)

    # 使用 weakref 避免内存泄漏
    _active_combo_ref: weakref.ref | None = None

    def __init__(
        self,
        parent=None,
        max_visible_items: int = 8,
        *,
        multi_select: bool = False,
    ) -> None:
        super().__init__(parent)
        self._items: list[str] = []
        self._item_data: dict[int, Any] = {}
        self._current_index = 0
        self._checked_indices: set[int] = set()
        self._max_visible_items = max_visible_items
        self._min_display_text_px = 0
        self._app_filter_installed = False
        self._multi_select = multi_select
        self._placeholder_text = ""

        # 使用 QToolButton 作为触发器
        self._button = QToolButton()
        self._button.setObjectName("comboButton")
        self._button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._button.setMinimumWidth(0)
        self._button.clicked.connect(self._toggle_popup)

        # 无状态弹层列表
        self._popup = PopupList(self)
        self._popup.itemClicked.connect(self._on_popup_item_clicked)
        self._popup.installEventFilter(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._button, 1)

        self.setMinimumWidth(50)

    # ═══════════════════════════════════════════════════════════
    # 公共 API
    # ═══════════════════════════════════════════════════════════

    def addItems(self, items: list[str]) -> None:
        """批量添加列表项"""
        self._items = list(items)
        self._item_data.clear()
        self._current_index = 0
        self._checked_indices.clear()
        if items:
            self._update_display()
        else:
            self._update_display()
        self._sync_popup_selection()

    def setItemsWithData(self, items: list[tuple[str, Any]]) -> None:
        """批量设置带关联数据的列表项。"""
        self._items = []
        self._item_data.clear()
        self._current_index = 0
        self._checked_indices.clear()
        for index, (text, data) in enumerate(items):
            self._items.append(text)
            self._item_data[index] = data
        self._update_display()
        self._sync_popup_selection()

    def addItem(self, text: str, data: Any = None) -> None:
        """添加单个项"""
        index = len(self._items)
        self._items.append(text)
        if data is not None:
            self._item_data[index] = data
        if index == 0:
            self._update_display()

    def setItemData(self, index: int, data: Any) -> None:
        """设置项的关联数据"""
        if 0 <= index < len(self._items):
            self._item_data[index] = data

    def clear(self) -> None:
        """清空所有项"""
        self._items.clear()
        self._item_data.clear()
        self._current_index = 0
        self._checked_indices.clear()
        self._update_display()
        self._hide_popup()

    def setCurrentIndex(self, index: int) -> None:
        """设置当前索引"""
        if not (0 <= index < len(self._items)):
            return
        if index == self._current_index:
            return
        self._current_index = index
        self._update_display()
        self.currentIndexChanged.emit(index)
        self.currentTextChanged.emit(self.currentText())

    def currentIndex(self) -> int:
        return self._current_index

    def currentText(self) -> str:
        """返回当前文本"""
        if self._multi_select:
            texts = self.checkedTexts()
            return ", ".join(texts) if texts else self._placeholder_text
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return ""

    def currentData(self) -> Any:
        """获取当前项关联的数据"""
        if self._multi_select:
            return self.checkedData()
        return self._item_data.get(self._current_index)

    def count(self) -> int:
        """返回当前项数量。"""
        return len(self._items)

    def itemText(self, index: int) -> str:
        """返回指定索引的文本。"""
        if 0 <= index < len(self._items):
            return self._items[index]
        return ""

    def checkedTexts(self) -> list[str]:
        return [self._items[index] for index in sorted(self._checked_indices) if 0 <= index < len(self._items)]

    def checkedData(self) -> list[Any]:
        result: list[Any] = []
        for index in sorted(self._checked_indices):
            if not (0 <= index < len(self._items)):
                continue
            result.append(self._item_data.get(index, self._items[index]))
        return result

    def setCheckedData(self, values: list[Any]) -> None:
        targets = {str(value) for value in values if str(value).strip()}
        self._checked_indices = {
            index
            for index in range(len(self._items))
            if str(self._item_data.get(index, self._items[index])) in targets
        }
        self._update_display()
        self._sync_popup_selection()

    def setPlaceholderText(self, text: str) -> None:
        self._placeholder_text = text
        self._update_display()

    def maxItemTextWidth(self) -> int:
        """返回当前列表项最大文本像素宽度。"""
        if not self._items:
            return 0
        metrics = self._button.fontMetrics()
        return max(metrics.horizontalAdvance(text) for text in self._items)

    def setDisplayMinTextWidth(self, pixels: int) -> None:
        """设置显示文本的最小像素宽度（用于列内视觉对齐）。"""
        self._min_display_text_px = max(0, int(pixels))
        self._update_display()

    def findText(self, text: str) -> int:
        """查找文本对应的索引"""
        try:
            return self._items.index(text)
        except ValueError:
            return -1

    def showPopup(self) -> None:
        """显示弹层"""
        self._show_popup()

    def hidePopup(self) -> None:
        """隐藏弹层"""
        self._hide_popup()

    def isPopupVisible(self) -> bool:
        """弹层是否可见"""
        return self._popup.isVisible()

    def popupGeometryGlobal(self) -> QRect:
        """返回弹层的全局几何矩形"""
        return self._popup.global_geometry()

    # ═══════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════

    def _update_display(self) -> None:
        """更新显示文本"""
        if self._multi_select:
            checked_texts = self.checkedTexts()
            if not checked_texts:
                text = self._placeholder_text
                tooltip_text = ""
            else:
                text = ", ".join(checked_texts)
                tooltip_text = text
        elif self._items and 0 <= self._current_index < len(self._items):
            text = self._items[self._current_index]
            tooltip_text = text
        else:
            text = ""
            tooltip_text = ""

        if text:
            metrics = self._button.fontMetrics()
            available = max(
                12,
                self._button.contentsRect().width(),
                self._button.width(),
                self.width(),
            )
            suffix_text = " ⌵"
            suffix_width = metrics.horizontalAdvance(suffix_text)
            body_available = max(8, available - suffix_width)
            elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, body_available)

            # 通过空格补齐最小显示宽度，使同列下拉文本视觉上左对齐更稳定
            target_body_px = min(self._min_display_text_px, body_available)
            padded_body = elided
            while (
                metrics.horizontalAdvance(padded_body) < target_body_px
                and metrics.horizontalAdvance(padded_body + " ") <= body_available
            ):
                padded_body += " "

            full_text = f"{padded_body}{suffix_text}"
            while len(padded_body) > len(elided) and metrics.horizontalAdvance(full_text) > available:
                padded_body = padded_body[:-1]
                full_text = f"{padded_body}{suffix_text}"

            self._button.setText(full_text)
            self._button.setToolTip(tooltip_text or text)
        else:
            self._button.setText("")
            self._button.setToolTip("")

    def _sync_popup_selection(self) -> None:
        """同步弹层选中状态"""
        if self._popup.isVisible():
            if self._multi_select:
                self._popup.set_checked(self._checked_indices)
            else:
                self._popup.set_selected(self._current_index)

    def _toggle_popup(self) -> None:
        """切换弹层显示状态"""
        if self._popup.isVisible():
            self._hide_popup()
        else:
            self._show_popup()

    def _show_popup(self) -> None:
        """显示弹层列表"""
        if not self._items:
            return

        # 关闭其他活动的 combo
        active = CustomComboBox._get_active_combo()
        if active is not None and active is not self:
            active.hidePopup()

        # 设置弹层内容
        self._popup.set_items(
            self._items,
            self._current_index,
            checked_indices=self._checked_indices,
            multi_select=self._multi_select,
        )
        self._popup.setFixedWidth(self.width())

        # 计算弹层高度
        content_height = self._popup.content_height(self._max_visible_items)
        popup_height = max(24, content_height)
        self._popup.list_widget.setFixedHeight(content_height)
        self._popup.list_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if len(self._items) > self._max_visible_items
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._popup.setMinimumHeight(0)
        self._popup.setMaximumHeight(popup_height)
        self._popup.setFixedHeight(popup_height)

        # 先显示，再按固定高度定位，避免小列表出现额外留白
        self._popup.show()

        # 计算位置
        button_global = self._button.mapToGlobal(QPoint(0, 0))
        popup_height = self._popup.height()
        popup_x = button_global.x()
        popup_y = button_global.y() + self._button.height()

        # 屏幕边界检测
        screen = QApplication.screenAt(button_global)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            screen_rect = screen.availableGeometry()
            if popup_y + popup_height > screen_rect.bottom():
                popup_y = button_global.y() - popup_height
            if popup_x + self._popup.width() > screen_rect.right():
                popup_x = screen_rect.right() - self._popup.width()
            if popup_x < screen_rect.left():
                popup_x = screen_rect.left()
            if popup_y < screen_rect.top():
                popup_y = screen_rect.top()

        self._popup.move(QPoint(popup_x, popup_y))
        self._popup.raise_()

        self._install_app_event_filter()
        CustomComboBox._set_active_combo(self)

    def _on_popup_item_clicked(self, index: int) -> None:
        """弹层项被点击"""
        if not (0 <= index < len(self._items)):
            return

        if self._multi_select:
            if index in self._checked_indices:
                self._checked_indices.remove(index)
            else:
                self._checked_indices.add(index)
            self._update_display()
            self.currentTextChanged.emit(self.currentText())
            self._sync_popup_selection()
            return

        self._hide_popup()
        if index != self._current_index:
            self._current_index = index
            self._update_display()
            self.currentIndexChanged.emit(index)
            self.currentTextChanged.emit(self.currentText())

    def _hide_popup(self) -> None:
        """隐藏弹层"""
        if not hasattr(self, "_popup"):
            return
        if self._popup.isVisible():
            self._popup.hide()
        if CustomComboBox._get_active_combo() is self:
            CustomComboBox._clear_active_combo()
        self._remove_app_event_filter()

    @classmethod
    def _get_active_combo(cls) -> "CustomComboBox | None":
        """获取当前活动的 combo"""
        if cls._active_combo_ref is None:
            return None
        return cls._active_combo_ref()

    @classmethod
    def _set_active_combo(cls, combo: "CustomComboBox") -> None:
        """设置当前活动的 combo"""
        cls._active_combo_ref = weakref.ref(combo)

    @classmethod
    def _clear_active_combo(cls) -> None:
        """清除活动 combo 引用"""
        cls._active_combo_ref = None

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
        """事件过滤器：处理弹层隐藏和外部点击"""
        # 弹层自身隐藏时，清理状态
        if obj is self._popup and event.type() == QEvent.Type.Hide:
            if CustomComboBox._get_active_combo() is self:
                CustomComboBox._clear_active_combo()
            self._remove_app_event_filter()
            return super().eventFilter(obj, event)

        # 处理外部点击
        if self._popup.isVisible() and event.type() == QEvent.Type.MouseButtonPress:
            global_pos = self._event_global_pos(event)
            if global_pos is not None:
                popup_rect = self._popup.global_geometry()
                button_rect = QRect(
                    self._button.mapToGlobal(QPoint(0, 0)),
                    self._button.size()
                )
                # 点击在 popup 和 button 之外 → 关闭 popup
                if not popup_rect.contains(global_pos) and not button_rect.contains(global_pos):
                    self._hide_popup()
                    # 返回 False 让事件继续传播（可能触发外层 dialog 关闭）
                    return False

        return super().eventFilter(obj, event)

    def _event_global_pos(self, event) -> QPoint | None:
        """获取事件的全局坐标"""
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        if hasattr(event, "globalPos"):
            return event.globalPos()
        return None

    def hideEvent(self, event) -> None:
        self._hide_popup()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._hide_popup()
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        self._update_display()
        super().showEvent(event)

    def resizeEvent(self, event) -> None:
        self._update_display()
        super().resizeEvent(event)
