from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


@dataclass
class UiTaskSpec:
    lane: str
    generation: int
    single_flight: bool
    fn: Callable[[], Any]


class _TaskWorker(QRunnable):
    def __init__(self, runner: "UiTaskRunner", spec: UiTaskSpec) -> None:
        super().__init__()
        self._runner = runner
        self._spec = spec

    def run(self) -> None:
        try:
            payload = self._spec.fn()
        except Exception as exc:  # pragma: no cover - exercised by later controller tests
            self._runner._handle_error(self._spec, str(exc))
        else:
            self._runner._handle_result(self._spec, payload)
        finally:
            self._runner._handle_finished(self._spec)


class UiTaskRunner(QObject):
    result_ready = Signal(str, int, object)
    error_ready = Signal(str, int, str)
    busy_changed = Signal(str, bool)

    def __init__(self, *, thread_pool: QThreadPool | None = None) -> None:
        super().__init__()
        self._pool = thread_pool or QThreadPool.globalInstance()
        self._latest_generation: dict[str, int] = {}
        self._busy_lanes: set[str] = set()

    def submit(self, spec: UiTaskSpec) -> bool:
        if spec.single_flight and spec.lane in self._busy_lanes:
            return False

        self._latest_generation[spec.lane] = spec.generation
        if spec.single_flight:
            self._busy_lanes.add(spec.lane)
            self.busy_changed.emit(spec.lane, True)

        self._pool.start(_TaskWorker(self, spec))
        return True

    def _handle_result(self, spec: UiTaskSpec, payload: object) -> None:
        if self._latest_generation.get(spec.lane) != spec.generation:
            return
        self.result_ready.emit(spec.lane, spec.generation, payload)

    def _handle_error(self, spec: UiTaskSpec, message: str) -> None:
        if self._latest_generation.get(spec.lane) != spec.generation:
            return
        self.error_ready.emit(spec.lane, spec.generation, message)

    def _handle_finished(self, spec: UiTaskSpec) -> None:
        if spec.single_flight and spec.lane in self._busy_lanes:
            self._busy_lanes.remove(spec.lane)
            self.busy_changed.emit(spec.lane, False)
