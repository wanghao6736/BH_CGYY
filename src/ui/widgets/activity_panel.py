from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
                               QVBoxLayout)


class _LogRelay(QObject):
    message_logged = Signal(str)


class _QtLogHandler(logging.Handler):
    def __init__(self, relay: _LogRelay) -> None:
        super().__init__(level=logging.INFO)
        self._relay = relay

    def emit(self, record: logging.LogRecord) -> None:
        if self._relay is None:
            return
        try:
            message = self.format(record)
        except Exception:
            self.handleError(record)
            return
        if message.strip():
            try:
                self._relay.message_logged.emit(message)
            except RuntimeError:
                self._relay = None

    def close(self) -> None:
        self._relay = None
        super().close()


class ActivityPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("activityPanel", "true")
        self.hide()

        self._relay = _LogRelay(self)
        self._relay.message_logged.connect(self.append_message)

        self.title_label = QLabel("📝 Activity")
        self.title_label.setProperty("role", "subtitle")

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(200)
        self.output.setMinimumHeight(88)
        self.output.setPlaceholderText("等待输出...")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addLayout(title_layout)
        layout.addWidget(self.output)

    def create_log_handler(self) -> logging.Handler:
        handler = _QtLogHandler(self._relay)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        return handler

    def append_message(self, message: str) -> None:
        text = (message or "").strip()
        if not text:
            return
        if self.isHidden():
            self.show()
        self.output.appendPlainText(text)
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()
