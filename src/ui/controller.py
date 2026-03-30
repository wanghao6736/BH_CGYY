from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.ui.facade import BoardQuery, ReserveRequest, UiFacade
from src.ui.state import (PollingState, PollingStatus, ReserveOutcome,
                          SessionState, SettingsFormState)
from src.ui.tasks import UiTaskRunner, UiTaskSpec


class UiController(QObject):
    session_loaded = Signal(int, object)
    board_loaded = Signal(int, object)
    reserve_finished = Signal(int, object)
    settings_loaded = Signal(int, object)
    polling_state_changed = Signal(object)
    lane_busy_changed = Signal(str, bool)
    lane_failed = Signal(str, int, str)

    def __init__(self, facade: UiFacade, *, runner: UiTaskRunner | None = None) -> None:
        super().__init__()
        self._facade = facade
        self._runner = runner or UiTaskRunner()
        self._generations = {
            "session": 0,
            "board": 0,
            "reserve": 0,
            "settings": 0,
            "polling": 0,
        }
        self.polling_state = PollingState()
        self._runner.result_ready.connect(self._handle_result)
        self._runner.error_ready.connect(self._handle_error)
        self._runner.busy_changed.connect(self.lane_busy_changed.emit)

    def _next_generation(self, lane: str) -> int:
        self._generations[lane] += 1
        return self._generations[lane]

    def request_session_probe(self, profile_name: str) -> int:
        generation = self._next_generation("session")
        self._runner.submit(
            UiTaskSpec(
                lane="session",
                generation=generation,
                single_flight=False,
                fn=lambda: self._facade.get_session_state(profile_name),
            )
        )
        return generation

    def request_login(self, profile_name: str, username: str, password: str) -> int | None:
        generation = self._next_generation("session")
        started = self._runner.submit(
            UiTaskSpec(
                lane="session",
                generation=generation,
                single_flight=True,
                fn=lambda: self._facade.login(profile_name, username, password),
            )
        )
        return generation if started else None

    def request_logout(self, profile_name: str) -> int | None:
        generation = self._next_generation("session")
        started = self._runner.submit(
            UiTaskSpec(
                lane="session",
                generation=generation,
                single_flight=True,
                fn=lambda: self._facade.logout(profile_name),
            )
        )
        return generation if started else None

    def request_board_refresh(self, query: BoardQuery) -> int:
        generation = self._next_generation("board")
        self._runner.submit(
            UiTaskSpec(
                lane="board",
                generation=generation,
                single_flight=False,
                fn=lambda: self._facade.load_board(query),
            )
        )
        return generation

    def request_reserve(self, request: ReserveRequest) -> int | None:
        generation = self._next_generation("reserve")
        started = self._runner.submit(
            UiTaskSpec(
                lane="reserve",
                generation=generation,
                single_flight=True,
                fn=lambda: self._facade.reserve(request),
            )
        )
        return generation if started else None

    def request_save_settings(self, state: SettingsFormState) -> int | None:
        generation = self._next_generation("settings")
        started = self._runner.submit(
            UiTaskSpec(
                lane="settings",
                generation=generation,
                single_flight=True,
                fn=lambda: self._facade.save_profile_patch(state),
            )
        )
        return generation if started else None

    def request_start_polling(self, query: BoardQuery, *, interval_sec: int = 8) -> int | None:
        if self.polling_state.status in {PollingStatus.STARTING, PollingStatus.RUNNING}:
            return None
        generation = self._next_generation("polling")
        self.polling_state = PollingState(
            status=PollingStatus.STARTING,
            interval_sec=max(1, interval_sec),
            last_checked_at=self.polling_state.last_checked_at,
            last_message="轮询启动中",
        )
        self.polling_state_changed.emit(self.polling_state)
        return generation

    def request_stop_polling(self) -> int | None:
        if self.polling_state.status in {PollingStatus.STOPPING, PollingStatus.STOPPED}:
            return None
        generation = self._next_generation("polling")
        self.polling_state = PollingState(
            status=PollingStatus.STOPPING,
            interval_sec=self.polling_state.interval_sec,
            last_checked_at=self.polling_state.last_checked_at,
            last_message="轮询停止中",
        )
        self.polling_state_changed.emit(self.polling_state)
        return generation

    def set_polling_running(self) -> None:
        self.polling_state = PollingState(
            status=PollingStatus.RUNNING,
            interval_sec=self.polling_state.interval_sec,
            last_checked_at=self.polling_state.last_checked_at,
            last_message=self.polling_state.last_message or "轮询运行中",
        )
        self.polling_state_changed.emit(self.polling_state)

    def set_polling_stopped(self, message: str = "已停止") -> None:
        self.polling_state = PollingState(
            status=PollingStatus.STOPPED,
            interval_sec=self.polling_state.interval_sec,
            last_checked_at=self.polling_state.last_checked_at,
            last_message=message,
        )
        self.polling_state_changed.emit(self.polling_state)

    def update_polling_check(self, *, checked_at: str, message: str) -> None:
        self.polling_state = PollingState(
            status=PollingStatus.RUNNING,
            interval_sec=self.polling_state.interval_sec,
            last_checked_at=checked_at,
            last_message=message,
        )
        self.polling_state_changed.emit(self.polling_state)

    def _handle_result(self, lane: str, generation: int, payload: object) -> None:
        if lane == "session":
            self.session_loaded.emit(generation, payload)
        elif lane == "board":
            self.board_loaded.emit(generation, payload)
        elif lane == "reserve":
            self.reserve_finished.emit(generation, payload)
        elif lane == "settings":
            self.settings_loaded.emit(generation, payload)

    def _handle_error(self, lane: str, generation: int, message: str) -> None:
        self.lane_failed.emit(lane, generation, message)
