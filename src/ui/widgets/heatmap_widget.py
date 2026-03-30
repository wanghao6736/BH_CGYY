"""热力图绘制组件：使用自定义绘制实现紧凑网格展示场地状态"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

if TYPE_CHECKING:
    pass


class CellStatus(Enum):
    """单元格状态枚举"""
    AVAILABLE = 1      # 可预定（空闲）
    LOCKED = 2         # 系统锁定
    PENDING = 3        # 待付款
    RESERVED = 4       # 已被预定
    UNKNOWN = 0        # 未知


# 状态对应的符号
STATUS_SYMBOLS = {
    CellStatus.AVAILABLE: "",      # 空闲不显示符号
    CellStatus.LOCKED: "🔒",        # 系统锁定
    CellStatus.PENDING: "⏳",      # 待付款
    CellStatus.RESERVED: "❌",     # 已预定
    CellStatus.UNKNOWN: "❓",       # 未知
}

# 默认状态颜色（可通过 QSS 覆盖）
DEFAULT_COLORS = {
    CellStatus.AVAILABLE: "#E6F6F6",
    CellStatus.LOCKED: "#F5EEE8",
    CellStatus.PENDING: "#FFF7E6",
    CellStatus.RESERVED: "#FEECEC",
    CellStatus.UNKNOWN: "#F5EEE8",
    "range_blocked": "#FBE4E6",
    "available_muted": "#E5E7EB",
    "border_available": "#7CC9C8",
    "selected": "#0EA5A4",
    "border": "#D1D5DB",
    "border_range_blocked": "#E7A6AF",
    "border_hover": "#334155",
    "header_bg": "#F9FAFB",
    "header_text": "#6B7280",
}


@dataclass
class HeatCell:
    """热力图单元格数据模型"""
    status: CellStatus = CellStatus.AVAILABLE
    enabled: bool = True
    range_blocked: bool = False
    selected: bool = False
    tooltip: str = ""

    def symbol(self) -> str:
        """获取状态对应的符号"""
        if self.selected:
            return "✅"
        return STATUS_SYMBOLS.get(self.status, "")


@dataclass
class HeatmapConfig:
    """热力图配置参数"""
    cell_w: int = 24
    cell_h: int = 24
    gap: int = 2
    radius: int = 4
    header_w: int = 50
    header_h: int = 20
    padding: int = 8


class HeatmapWidget(QWidget):
    """热力图绘制组件

    使用自定义绘制实现紧凑的网格布局，支持：
    - 行头（场地名称）和列头（时间段）
    - 状态颜色映射
    - 状态符号显示
    - 鼠标悬停和点击交互
    """

    cellClicked = Signal(int, int)  # (row, col)
    cellHovered = Signal(int, int)
    selectionChanged = Signal(object)  # list[tuple[int, int]]

    def __init__(
        self,
        rows: int = 0,
        cols: int = 0,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        self._cells: list[list[HeatCell]] = []
        self._row_headers: list[str] = []
        self._col_headers: list[str] = []

        self._config = HeatmapConfig()
        self._colors = DEFAULT_COLORS.copy()

        self._hovered: Optional[tuple[int, int]] = None
        self._pressed: Optional[tuple[int, int]] = None

        self.setMouseTracking(True)
        self._init_cells()

    def _init_cells(self) -> None:
        """初始化单元格矩阵"""
        self._cells = [
            [HeatCell() for _ in range(self._cols)]
            for _ in range(self._rows)
        ]

    def set_dimensions(self, rows: int, cols: int) -> None:
        """设置矩阵维度"""
        self._rows = rows
        self._cols = cols
        self._init_cells()
        self.updateGeometry()
        self.update()

    def set_headers(
        self,
        row_headers: list[str],
        col_headers: list[str]
    ) -> None:
        """设置表头"""
        self._row_headers = row_headers
        self._col_headers = col_headers
        self.update()

    def set_cell(self, row: int, col: int, cell: HeatCell) -> None:
        """设置单个单元格"""
        if 0 <= row < self._rows and 0 <= col < self._cols:
            self._cells[row][col] = cell
            self.update()

    def set_cells(self, cells: list[list[HeatCell]]) -> None:
        """批量设置单元格"""
        self._cells = cells
        self._rows = len(cells)
        self._cols = len(cells[0]) if self._rows > 0 else 0
        self.updateGeometry()
        self.update()

    def get_cell(self, row: int, col: int) -> Optional[HeatCell]:
        """获取单个单元格"""
        if 0 <= row < self._rows and 0 <= col < self._cols:
            return self._cells[row][col]
        return None

    def clear_selection(self) -> None:
        """清除所有选中状态"""
        for row in self._cells:
            for cell in row:
                cell.selected = False
        self.update()

    def get_selected_cells(self) -> list[tuple[int, int]]:
        """获取所有选中的单元格坐标"""
        result = []
        for r, row in enumerate(self._cells):
            for c, cell in enumerate(row):
                if cell.selected:
                    result.append((r, c))
        return result

    def set_color(self, key: str, color: str) -> None:
        """设置颜色配置"""
        if key in self._colors:
            self._colors[key] = color
            self.update()

    def set_colors(self, colors: dict) -> None:
        """批量设置颜色配置"""
        self._colors.update(colors)
        self.update()

    # ==================== 尺寸计算 ====================

    def sizeHint(self) -> QSize:
        """计算推荐尺寸"""
        cfg = self._config
        w = cfg.padding * 2
        h = cfg.padding * 2

        # 列头高度
        if self._col_headers:
            h += cfg.header_h

        # 行头宽度
        if self._row_headers:
            w += cfg.header_w

        # 数据区域
        if self._cols > 0:
            w += self._cols * cfg.cell_w + (self._cols - 1) * cfg.gap
        if self._rows > 0:
            h += self._rows * cfg.cell_h + (self._rows - 1) * cfg.gap

        return QSize(w, h)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _cell_rect(self, row: int, col: int) -> QRect:
        """计算单元格绘制区域"""
        cfg = self._config
        x = cfg.padding
        y = cfg.padding

        # 偏移列头
        if self._col_headers:
            y += cfg.header_h + cfg.gap

        # 偏移行头
        if self._row_headers:
            x += cfg.header_w + cfg.gap

        # 计算单元格位置
        x += col * (cfg.cell_w + cfg.gap)
        y += row * (cfg.cell_h + cfg.gap)

        return QRect(x, y, cfg.cell_w, cfg.cell_h)

    def _row_header_rect(self, row: int) -> QRect:
        """计算行头绘制区域"""
        cfg = self._config
        cell_rect = self._cell_rect(row, 0)
        return QRect(
            cfg.padding,
            cell_rect.top(),
            cfg.header_w,
            cfg.cell_h
        )

    def _col_header_rect(self, col: int) -> QRect:
        """计算列头绘制区域"""
        cfg = self._config
        cell_rect = self._cell_rect(0, col)
        return QRect(
            cell_rect.left(),
            cfg.padding,
            cfg.cell_w,
            cfg.header_h
        )

    def _hit_test(self, pos: QPoint) -> Optional[tuple[int, int]]:
        """命中测试：判断坐标落在哪个单元格"""
        for r in range(self._rows):
            for c in range(self._cols):
                if self._cell_rect(r, c).contains(pos):
                    return (r, c)
        return None

    # ==================== 绘制 ====================

    def _get_cell_color(self, cell: HeatCell) -> QColor:
        """获取单元格背景色"""
        if cell.selected:
            return QColor(self._colors["selected"])
        if cell.range_blocked:
            return QColor(self._colors["range_blocked"])
        if not cell.enabled and cell.status is CellStatus.AVAILABLE:
            return QColor(self._colors["available_muted"])

        color_key = cell.status
        if isinstance(color_key, CellStatus):
            color_key = cell.status
        else:
            color_key = CellStatus.UNKNOWN

        color = self._colors.get(color_key, self._colors[CellStatus.UNKNOWN])
        return QColor(color)

    def paintEvent(self, event) -> None:
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # 填充背景
        painter.fillRect(self.rect(), self.palette().window())

        # 绘制列头
        self._draw_col_headers(painter)

        # 绘制行头
        self._draw_row_headers(painter)

        # 绘制数据单元格
        self._draw_cells(painter)

    def _draw_col_headers(self, painter: QPainter) -> None:
        """绘制列头（时间段）"""
        if not self._col_headers:
            return

        painter.save()
        painter.setPen(QColor(self._colors["header_text"]))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        for c, header in enumerate(self._col_headers):
            rect = self._col_header_rect(c)
            painter.fillRect(rect, QColor(self._colors["header_bg"]))
            painter.drawText(rect, Qt.AlignCenter, header)

        painter.restore()

    def _draw_row_headers(self, painter: QPainter) -> None:
        """绘制行头（场地名称）"""
        if not self._row_headers:
            return

        painter.save()
        painter.setPen(QColor(self._colors["header_text"]))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        for r, header in enumerate(self._row_headers):
            rect = self._row_header_rect(r)
            painter.fillRect(rect, QColor(self._colors["header_bg"]))
            painter.drawText(rect, Qt.AlignCenter | Qt.TextSingleLine, header)

        painter.restore()

    def _draw_cells(self, painter: QPainter) -> None:
        """绘制数据单元格"""
        for r in range(self._rows):
            for c in range(self._cols):
                self._draw_single_cell(painter, r, c)

    def _draw_single_cell(self, painter: QPainter, row: int, col: int) -> None:
        """绘制单个单元格"""
        cell = self._cells[row][col]
        rect = self._cell_rect(row, col)
        cfg = self._config

        # 背景色
        bg_color = self._get_cell_color(cell)

        # 边框色
        border_color = QColor(self._colors["border"])
        if cell.range_blocked:
            border_color = QColor(self._colors["border_range_blocked"])
        elif cell.enabled and cell.status is CellStatus.AVAILABLE:
            border_color = QColor(self._colors["border_available"])
        if self._hovered == (row, col) and cell.enabled:
            border_color = QColor(self._colors["border_hover"])

        # 绘制圆角矩形背景
        painter.save()
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, cfg.radius, cfg.radius)

        # 绘制符号
        symbol = cell.symbol()
        if symbol:
            painter.setPen(Qt.black if cell.selected else Qt.NoPen)
            if cell.selected:
                painter.setPen(QColor("#FFFFFF"))
            else:
                painter.setPen(QColor("#374151"))
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, symbol)

        painter.restore()

    # ==================== 鼠标交互 ====================

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """鼠标移动事件"""
        pos = event.position().toPoint()
        hovered = self._hit_test(pos)

        if hovered != self._hovered:
            self._hovered = hovered

            if hovered is not None:
                r, c = hovered
                self.cellHovered.emit(r, c)
                cell = self._cells[r][c]
                if cell.tooltip:
                    self.setToolTip(cell.tooltip)
                else:
                    self.setToolTip("")
            else:
                self.setToolTip("")

            self.update()

    def leaveEvent(self, event) -> None:
        """鼠标离开事件"""
        self._hovered = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """鼠标按下事件"""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        self._pressed = self._hit_test(pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """鼠标释放事件"""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.position().toPoint()
        released = self._hit_test(pos)

        if self._pressed is not None and self._pressed == released:
            r, c = released
            cell = self._cells[r][c]
            if cell.enabled:
                # 切换选中状态
                cell.selected = not cell.selected
                self.cellClicked.emit(r, c)
                self.selectionChanged.emit(self.get_selected_cells())
                self.update()

        self._pressed = None


if __name__ == "__main__":
    app = QApplication([])

    widget = HeatmapWidget(4, 8)

    # 设置表头
    widget.set_headers(
        row_headers=["场地1", "场地2", "场地3", "场地4"],
        col_headers=["8:00", "9:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
    )

    # 设置测试数据
    import random
    for r in range(4):
        for c in range(8):
            status = random.choice(list(CellStatus))
            widget.set_cell(r, c, HeatCell(
                status=status,
                enabled=True,
                tooltip=f"场地{r + 1} {['8:00', '9:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00'][c]}"
            ))

    widget.cellClicked.connect(lambda r, c: print(f"Clicked: ({r}, {c})"))
    widget.selectionChanged.connect(lambda cells: print(f"Selected: {cells}"))

    widget.show()
    app.exec()
