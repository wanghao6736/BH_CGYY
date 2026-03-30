from __future__ import annotations

from src.parsers.slot_filter import SlotChoice, SlotSolution
from src.ui.controller import UiController
from src.ui.facade import ReserveRequest


class DummySignal:
    def connect(self, callback) -> None:  # pragma: no cover - trivial stub
        self.callback = callback


class RejectingRunner:
    def __init__(self) -> None:
        self.result_ready = DummySignal()
        self.error_ready = DummySignal()
        self.busy_changed = DummySignal()

    def submit(self, spec) -> bool:
        return False

    def submit_background(self, fn, *, label: str = "") -> None:  # pragma: no cover - not used here
        raise AssertionError("should not be called")


class RecordingRunner:
    def __init__(self) -> None:
        self.result_ready = DummySignal()
        self.error_ready = DummySignal()
        self.busy_changed = DummySignal()
        self.background_calls = []

    def submit(self, spec) -> bool:
        return True

    def submit_background(self, fn, *, label: str = "") -> None:
        self.background_calls.append((fn, label))


class FakeFacade:
    def reserve(self, request) -> None:  # pragma: no cover - not called in this test
        raise AssertionError("should not be called")


def test_request_reserve_returns_none_when_single_flight_rejects() -> None:
    controller = UiController(FakeFacade(), runner=RejectingRunner())

    generation = controller.request_reserve(
        ReserveRequest(
            profile_name="default",
            venue_site_id=57,
            date="2026-03-22",
            solution=SlotSolution(
                choices=[
                    SlotChoice(space_id=101, time_id=1, start_time="18:00", end_time="18:30"),
                    SlotChoice(space_id=101, time_id=2, start_time="18:30", end_time="19:00"),
                ],
                total_fee=50.0,
                slot_count=2,
                total_hours=1.0,
            ),
        )
    )

    assert generation is None


def test_request_notification_runs_via_background_runner(monkeypatch) -> None:
    runner = RecordingRunner()
    controller = UiController(FakeFacade(), runner=runner)
    sent = []

    monkeypatch.setattr(
        "src.ui.controller.send_notification",
        lambda title, message, **kwargs: sent.append((title, message, kwargs)) or ["ios"],
    )

    controller.request_notification(
        "CGYY 预约成功",
        "message",
        profile_name="default",
    )

    assert len(runner.background_calls) == 1
    fn, label = runner.background_calls[0]
    assert label == "notification"
    fn()
    assert sent == [
        (
            "CGYY 预约成功",
            "message",
            {"profile_name": "default"},
        )
    ]
