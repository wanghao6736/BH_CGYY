from __future__ import annotations

import threading

from PySide6.QtWidgets import QApplication

from src.ui.tasks import UiTaskRunner, UiTaskSpec


def _pump_events(iterations: int = 50) -> None:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    for _ in range(iterations):
        app.processEvents()


class BlockingCall:
    def __init__(self, value: str) -> None:
        self.value = value
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(self) -> str:
        self.entered.set()
        self.release.wait(timeout=2)
        return self.value


def test_ui_tasks_latest_wins_for_board_refresh() -> None:
    runner = UiTaskRunner()
    applied: list[str] = []
    old_call = BlockingCall("old")
    new_call = BlockingCall("new")

    runner.result_ready.connect(lambda lane, generation, payload: applied.append(payload))

    assert runner.submit(
        UiTaskSpec(
            lane="board",
            generation=1,
            single_flight=False,
            fn=old_call,
        )
    )
    assert old_call.entered.wait(timeout=1)

    assert runner.submit(
        UiTaskSpec(
            lane="board",
            generation=2,
            single_flight=False,
            fn=new_call,
        )
    )
    assert new_call.entered.wait(timeout=1)

    old_call.release.set()
    new_call.release.set()
    _pump_events()

    assert applied == ["new"]


def test_ui_tasks_session_probe_cannot_override_newer_login_result() -> None:
    runner = UiTaskRunner()
    applied: list[tuple[str, int, str]] = []
    probe_call = BlockingCall("probe")
    login_call = BlockingCall("login")

    runner.result_ready.connect(lambda lane, generation, payload: applied.append((lane, generation, payload)))

    assert runner.submit(
        UiTaskSpec(
            lane="session",
            generation=1,
            single_flight=False,
            fn=probe_call,
        )
    )
    assert probe_call.entered.wait(timeout=1)

    assert runner.submit(
        UiTaskSpec(
            lane="session",
            generation=2,
            single_flight=True,
            fn=login_call,
        )
    )
    assert login_call.entered.wait(timeout=1)

    probe_call.release.set()
    login_call.release.set()
    _pump_events()

    assert applied == [("session", 2, "login")]


def test_ui_tasks_reserve_is_single_flight() -> None:
    runner = UiTaskRunner()
    blocking_call = BlockingCall("first")

    assert runner.submit(
        UiTaskSpec(
            lane="reserve",
            generation=1,
            single_flight=True,
            fn=blocking_call,
        )
    )
    assert blocking_call.entered.wait(timeout=1)

    assert not runner.submit(
        UiTaskSpec(
            lane="reserve",
            generation=2,
            single_flight=True,
            fn=lambda: "second",
        )
    )

    blocking_call.release.set()
    _pump_events()


def test_ui_tasks_settings_is_single_flight() -> None:
    runner = UiTaskRunner()
    blocking_call = BlockingCall("first")

    assert runner.submit(
        UiTaskSpec(
            lane="settings",
            generation=1,
            single_flight=True,
            fn=blocking_call,
        )
    )
    assert blocking_call.entered.wait(timeout=1)

    assert not runner.submit(
        UiTaskSpec(
            lane="settings",
            generation=2,
            single_flight=True,
            fn=lambda: "second",
        )
    )

    blocking_call.release.set()
    _pump_events()
