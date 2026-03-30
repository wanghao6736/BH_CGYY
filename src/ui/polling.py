from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from src.ui.facade import BoardQuery
from src.ui.state import PollingState, PollingStatus


@dataclass
class PollTickResult:
    checked_at: str
    message: str


class PollingCoordinator(QObject):
    state_changed = Signal(object)
    tick_requested = Signal(object)

    def __init__(self, *, on_tick: Callable[[BoardQuery], None], interval_sec: int = 8) -> None:
        super().__init__()
        self._on_tick = on_tick
        self._query: BoardQuery | None = None
        self._state = PollingState(interval_sec=max(1, interval_sec))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)

    @property
    def state(self) -> PollingState:
        return self._state

    def start(self, query: BoardQuery) -> bool:
        if self._timer.isActive():
            return False
        self._query = query
        self._state = PollingState(
            status=PollingStatus.STARTING,
            interval_sec=self._state.interval_sec,
            last_checked_at=self._state.last_checked_at,
            last_message="轮询启动中",
        )
        self.state_changed.emit(self._state)
        self._timer.start(self._state.interval_sec * 1000)
        self._state = PollingState(
            status=PollingStatus.RUNNING,
            interval_sec=self._state.interval_sec,
            last_checked_at=self._state.last_checked_at,
            last_message="轮询运行中",
        )
        self.state_changed.emit(self._state)
        return True

    def stop(self) -> bool:
        if not self._timer.isActive() and self._state.status is PollingStatus.STOPPED:
            return False
        self._timer.stop()
        self._state = PollingState(
            status=PollingStatus.STOPPED,
            interval_sec=self._state.interval_sec,
            last_checked_at=self._state.last_checked_at,
            last_message="已停止",
        )
        self.state_changed.emit(self._state)
        return True

    def _on_timeout(self) -> None:
        if self._query is None:
            return
        checked_at = datetime.now().strftime("%H:%M:%S")
        self._state = PollingState(
            status=PollingStatus.RUNNING,
            interval_sec=self._state.interval_sec,
            last_checked_at=checked_at,
            last_message="轮询检查完成",
        )
        self.state_changed.emit(self._state)
        self.tick_requested.emit(self._query)
        self._on_tick(self._query)

    def _on_timeout_for_test(self) -> None:
        self._on_timeout()
