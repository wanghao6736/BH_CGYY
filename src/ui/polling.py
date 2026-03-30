from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from src.ui.facade import BoardQuery
from src.ui.state import PollingState, PollingStatus

logger = logging.getLogger(__name__)


def resolve_start_at(start_time: str, *, now: datetime | None = None) -> datetime | None:
    if not start_time:
        return None
    reference = now or datetime.now()
    try:
        hour, minute = map(int, start_time.split(":", 1))
    except ValueError:
        return None
    candidate = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate < reference and (candidate.hour, candidate.minute) != (reference.hour, reference.minute):
        candidate += timedelta(days=1)
    return candidate


class PollingCoordinator(QObject):
    state_changed = Signal(object)

    def __init__(
        self,
        *,
        on_tick: Callable[[BoardQuery], None],
        interval_sec: int = 8,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__()
        self._on_tick = on_tick
        self._now_factory = now_factory or datetime.now
        self._query: BoardQuery | None = None
        self._state = PollingState(interval_sec=max(1, interval_sec))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.timeout.connect(self._on_start_timer)

    @property
    def state(self) -> PollingState:
        return self._state

    def start(
        self,
        query: BoardQuery,
        *,
        interval_sec: int | None = None,
        start_at: datetime | None = None,
    ) -> bool:
        if self._timer.isActive() or self._start_timer.isActive():
            return False
        self._query = query
        next_interval_sec = max(1, interval_sec) if interval_sec is not None else self._state.interval_sec
        delay_ms = 0
        message = "轮询启动中"
        if start_at is not None:
            delay_ms = max(0, int((start_at - self._now_factory()).total_seconds() * 1000))
            if delay_ms > 0:
                message = f"等待至 {start_at:%H:%M} 开始"
        self._state = PollingState(
            status=PollingStatus.STARTING,
            interval_sec=next_interval_sec,
            last_checked_at=self._state.last_checked_at,
            last_message=message,
        )
        self.state_changed.emit(self._state)
        if delay_ms > 0:
            self._start_timer.start(delay_ms)
            logger.info("轮询已计划 start_at=%s interval=%ss", start_at.strftime("%H:%M"), next_interval_sec)
            return True
        self._begin_running(trigger_check=start_at is not None)
        return True

    def stop(self) -> bool:
        if not self._timer.isActive() and not self._start_timer.isActive() and self._state.status is PollingStatus.STOPPED:
            return False
        self._start_timer.stop()
        self._timer.stop()
        self._state = PollingState(
            status=PollingStatus.STOPPED,
            interval_sec=self._state.interval_sec,
            last_checked_at=self._state.last_checked_at,
            last_message="已停止",
        )
        self.state_changed.emit(self._state)
        logger.info("轮询已停止")
        return True

    def record_check(self, *, checked_at: str = "", message: str = "检查完成") -> bool:
        if self._state.status is not PollingStatus.RUNNING:
            return False
        next_checked_at = checked_at or self._state.last_checked_at or datetime.now().strftime("%H:%M:%S")
        self._state = PollingState(
            status=PollingStatus.RUNNING,
            interval_sec=self._state.interval_sec,
            last_checked_at=next_checked_at,
            last_message=message,
        )
        self.state_changed.emit(self._state)
        logger.info("轮询状态: %s", message)
        return True

    def _on_timeout(self) -> None:
        if self._query is None:
            return
        checked_at = self._now_factory().strftime("%H:%M:%S")
        self._state = PollingState(
            status=PollingStatus.RUNNING,
            interval_sec=self._state.interval_sec,
            last_checked_at=checked_at,
            last_message="轮询检查完成",
        )
        self.state_changed.emit(self._state)
        self._on_tick(self._query)

    def _begin_running(self, *, trigger_check: bool) -> None:
        self._timer.start(self._state.interval_sec * 1000)
        self._state = PollingState(
            status=PollingStatus.RUNNING,
            interval_sec=self._state.interval_sec,
            last_checked_at=self._state.last_checked_at,
            last_message="轮询运行中",
        )
        self.state_changed.emit(self._state)
        logger.info("轮询已启动 interval=%ss", self._state.interval_sec)
        if trigger_check:
            self._on_timeout()

    def _on_start_timer(self) -> None:
        self._begin_running(trigger_check=True)

    def _on_timeout_for_test(self) -> None:
        self._on_timeout()

    def _on_start_timer_for_test(self) -> None:
        self._on_start_timer()
