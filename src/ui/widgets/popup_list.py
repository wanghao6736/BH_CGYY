"""弹出列表基类，纯视图，无状态"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QVBoxLayout


class PopupList(QFrame):
    """弹出列表 - 纯视图，无状态存储"""

    itemClicked = Signal(int)  # 用户点击某项，传递索引

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("popupList")

        self._list_widget = QListWidget()
        self._multi_select = False
        self._list_widget.setObjectName("popupListView")
        self._list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_widget.itemClicked.connect(self._on_item_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list_widget)
        self.hide()

    @property
    def list_widget(self) -> QListWidget:
        """暴露 list_widget 用于高度计算（向后兼容）"""
        return self._list_widget

    def set_items(
        self,
        items: list[str],
        selected_index: int = -1,
        *,
        checked_indices: set[int] | None = None,
        multi_select: bool = False,
    ) -> None:
        """设置列表项（纯渲染，不存储状态）"""
        self._multi_select = multi_select
        checked = checked_indices or set()
        self._list_widget.clear()
        for i, text in enumerate(items):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, text)
            if self._multi_select:
                self._set_checked_state(item, i in checked)
            else:
                item.setText(text)
                if i == selected_index:
                    item.setSelected(True)
            self._list_widget.addItem(item)
        if not self._multi_select and 0 <= selected_index < len(items):
            self._list_widget.setCurrentRow(selected_index)

    def set_selected(self, index: int) -> None:
        """设置选中项"""
        if not self._multi_select:
            self._list_widget.setCurrentRow(index)

    def set_checked(self, indices: set[int]) -> None:
        """设置多选勾选状态。"""
        if not self._multi_select:
            return
        for row in range(self._list_widget.count()):
            item = self._list_widget.item(row)
            self._set_checked_state(item, row in indices)

    def _set_checked_state(self, item: QListWidgetItem, checked: bool) -> None:
        text = str(item.data(Qt.ItemDataRole.UserRole) or "")
        item.setData(Qt.ItemDataRole.UserRole + 1, checked)
        item.setText(f"✓ {text}" if checked else text)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """点击项时，通知父组件"""
        index = self._list_widget.row(item)
        self.itemClicked.emit(index)

    def show_at(self, pos: QPoint) -> None:
        """在指定位置显示"""
        self.move(pos)
        self.show()

    def content_height(self, max_rows: int = 8) -> int:
        """计算内容高度"""
        count = self._list_widget.count()
        if count == 0:
            return 0
        row_height = self._list_widget.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 24
        visible_rows = min(count, max_rows)
        frame = self._list_widget.frameWidth() * 2
        return row_height * visible_rows + frame + 2

    def global_geometry(self) -> QRect:
        """返回全局坐标系下的几何矩形"""
        if not self.isVisible():
            return QRect()
        return QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
