"""详情热力图面板：底部弹出，非模态，点击外部关闭，支持拖动"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.ui.state import BoardCell, BoardState, SelectionState
from src.ui.ui_mappers import build_panel_selection_summary, resolve_enabled_choice_keys
from src.ui.widgets.bottom_popup import BottomPopup
from src.ui.widgets.heatmap_widget import CellStatus, HeatCell, HeatmapWidget


class BoardPanel(BottomPopup):
    """详情热力图面板 - 底部弹出，非模态，点击外部关闭，支持拖动

    布局结构:
    ┌─────────────────────────────────────────┐
    │ 时段详情              最后同步: 10:30   │
    ├─────────────────────────────────────────┤
    │ [HeatmapWidget - 热力图网格]            │
    └─────────────────────────────────────────┘
    """

    cellClicked = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("boardPanel", "true")

        # 内部容器（用于圆角边框）
        self.body = QFrame(self)
        self.body.setProperty("boardPanelBody", "true")

        # 标题栏
        self.title_label = QLabel("🕐 时段详情")
        self.title_label.setProperty("role", "subtitle")

        self.sync_label = QLabel("⚠️ 未同步")
        self.sync_label.setProperty("role", "muted")

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.sync_label)

        # 热力图组件
        self.heatmap = HeatmapWidget()
        self.heatmap.cellClicked.connect(self.cellClicked.emit)

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

    def _set_sync_text(self, text: str) -> None:
        """设置同步时间文本"""
        self.sync_label.setText(text or "未同步")

    def _set_selection_summary(self, text: str) -> None:
        """设置选择摘要文本"""
        self.selection_summary.setText(text or "点击单元格选择时段")

    def apply_board_state(
        self,
        state: BoardState | None,
        selection_state: SelectionState | None = None,
    ) -> None:
        if state is None:
            self._set_sync_text("")
            self._set_selection_summary("点击单元格选择时段")
            self.heatmap.set_dimensions(0, 0)
            self.heatmap.set_headers([], [])
            return

        sync_text = f"{state.last_sync_at or '-'}"
        self._set_sync_text(sync_text)

        rows = len(state.rows)
        cols = len(state.time_headers) if state.time_headers else 0
        self.heatmap.set_dimensions(rows, cols)
        self.heatmap.set_headers(
            row_headers=[row.space_name for row in state.rows],
            col_headers=state.time_headers,
        )

        selected_slots = self._selected_slots(selection_state)
        enabled_slots = resolve_enabled_choice_keys(state, selection_state)
        for row_index, row in enumerate(state.rows):
            for col_index, cell in enumerate(row.cells):
                key = (cell.space_id, cell.time_id)
                self.heatmap.set_cell(
                    row_index,
                    col_index,
                    HeatCell(
                        status=self._map_cell_status(cell),
                        enabled=key in enabled_slots,
                        range_blocked=cell.range_blocked,
                        selected=key in selected_slots,
                        tooltip=self._build_tooltip(cell, enabled=key in enabled_slots),
                    ),
                )

        self._set_selection_summary(build_panel_selection_summary(state, selection_state))

    def _map_cell_status(self, cell: BoardCell) -> CellStatus:
        if cell.reservation_status == 1:
            return CellStatus.AVAILABLE
        if cell.reservation_status == 2:
            return CellStatus.LOCKED
        if cell.reservation_status == 3:
            return CellStatus.PENDING
        if cell.reservation_status == 4:
            return CellStatus.RESERVED
        return CellStatus.UNKNOWN

    def _build_tooltip(self, cell: BoardCell, *, enabled: bool) -> str:
        tooltip = f"{cell.space_name} {cell.begin_time}-{cell.end_time}"
        if cell.range_blocked:
            return f"{tooltip}\n空闲，但不满足当前查询要求"
        if cell.reservation_status == 1 and not enabled:
            return f"{tooltip}\n空闲，但需先完成前序时段选择"
        return tooltip

    def _selected_slots(
        self,
        selection_state: SelectionState | None,
    ) -> set[tuple[int, int]]:
        if selection_state is None:
            return set()
        return {(choice.space_id, choice.time_id) for choice in selection_state.choices}

    def can_start_drag(self, local_pos) -> bool:
        title_rect = self.title_label.geometry().united(self.sync_label.geometry())
        title_rect.setLeft(0)
        title_rect.setRight(self.width())
        title_rect.setTop(0)
        return title_rect.contains(local_pos)
