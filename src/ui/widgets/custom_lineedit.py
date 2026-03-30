"""自定义输入框组件，统一视觉风格"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QToolButton


class CustomLineEdit(QFrame):
    """自定义输入框组件

    提供统一的视觉风格，与 CustomComboBox 保持一致。
    支持 placeholder 提示和可选的清除按钮。
    """

    textChanged = Signal(str)
    returnPressed = Signal()
    editingFinished = Signal()

    def __init__(
        self,
        parent=None,
        placeholder: str = "",
        clear_button: bool = False
    ) -> None:
        super().__init__(parent)
        self._clear_button_enabled = clear_button

        # 内部 QLineEdit
        self._line_edit = QLineEdit()
        self._line_edit.setObjectName("innerLineEdit")
        if placeholder:
            self._line_edit.setPlaceholderText(placeholder)

        # 清除按钮
        self._clear_button: Optional[QToolButton] = None
        if clear_button:
            self._clear_button = QToolButton()
            self._clear_button.setObjectName("clearButton")
            self._clear_button.setText("x")
            self._clear_button.setFixedWidth(20)
            self._clear_button.setCursor(Qt.CursorShape.ArrowCursor)
            self._clear_button.hide()
            self._clear_button.clicked.connect(self._on_clear_clicked)

        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._line_edit, 1)
        if self._clear_button:
            layout.addWidget(self._clear_button)

        # 连接信号
        self._line_edit.textChanged.connect(self._on_text_changed)
        self._line_edit.returnPressed.connect(self.returnPressed.emit)
        self._line_edit.editingFinished.connect(self.editingFinished.emit)

        self.setMinimumWidth(50)

    def _on_text_changed(self, text: str) -> None:
        """文本变化时更新清除按钮可见性"""
        if self._clear_button:
            self._clear_button.setVisible(bool(text) and self._clear_button_enabled)
        self.textChanged.emit(text)

    def _on_clear_clicked(self) -> None:
        """清除按钮点击"""
        self._line_edit.clear()
        self._line_edit.setFocus()

    # ═══════════════════════════════════════════════════════════
    # 公共 API（与 QLineEdit 兼容）
    # ═══════════════════════════════════════════════════════════

    def text(self) -> str:
        """获取文本内容"""
        return self._line_edit.text()

    def setText(self, text: str) -> None:
        """设置文本内容"""
        self._line_edit.setText(text)

    def placeholderText(self) -> str:
        """获取 placeholder 文本"""
        return self._line_edit.placeholderText()

    def setPlaceholderText(self, text: str) -> None:
        """设置 placeholder 文本"""
        self._line_edit.setPlaceholderText(text)

    def setClearButtonEnabled(self, enabled: bool) -> None:
        """设置是否启用清除按钮"""
        self._clear_button_enabled = enabled
        if self._clear_button:
            self._clear_button.setVisible(enabled and bool(self._line_edit.text()))

    def isClearButtonEnabled(self) -> bool:
        """获取清除按钮是否启用"""
        return self._clear_button_enabled

    def setReadOnly(self, readonly: bool) -> None:
        """设置只读状态"""
        self._line_edit.setReadOnly(readonly)

    def isReadOnly(self) -> bool:
        """获取是否只读"""
        return self._line_edit.isReadOnly()

    def setEnabled(self, enabled: bool) -> None:
        """设置启用状态"""
        super().setEnabled(enabled)
        self._line_edit.setEnabled(enabled)

    def setMaxLength(self, length: int) -> None:
        """设置最大长度"""
        self._line_edit.setMaxLength(length)

    def maxLength(self) -> int:
        """获取最大长度"""
        return self._line_edit.maxLength()

    def setEchoMode(self, mode: QLineEdit.EchoMode) -> None:
        """设置回显模式"""
        self._line_edit.setEchoMode(mode)

    def echoMode(self) -> QLineEdit.EchoMode:
        """获取回显模式"""
        return self._line_edit.echoMode()

    def setValidator(self, validator) -> None:
        """设置验证器"""
        self._line_edit.setValidator(validator)

    def validator(self):
        """获取验证器"""
        return self._line_edit.validator()

    def setAlignment(self, alignment: Qt.AlignmentFlag) -> None:
        """设置对齐方式"""
        self._line_edit.setAlignment(alignment)

    def alignment(self) -> Qt.AlignmentFlag:
        """获取对齐方式"""
        return self._line_edit.alignment()

    def selectAll(self) -> None:
        """全选文本"""
        self._line_edit.selectAll()

    def clear(self) -> None:
        """清空文本"""
        self._line_edit.clear()

    def setFocus(self) -> None:
        """设置焦点"""
        self._line_edit.setFocus()

    def setCursorPosition(self, pos: int) -> None:
        """设置光标位置"""
        self._line_edit.setCursorPosition(pos)

    def cursorPosition(self) -> int:
        """获取光标位置"""
        return self._line_edit.cursorPosition()
