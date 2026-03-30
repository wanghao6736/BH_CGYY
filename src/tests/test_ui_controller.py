from __future__ import annotations

from src.ui.controller import UiController
from src.ui.facade import BoardQuery, ReserveRequest
from src.ui.state import PollingStatus


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


class RecordingRunner:
    def __init__(self) -> None:
        self.result_ready = DummySignal()
        self.error_ready = DummySignal()
        self.busy_changed = DummySignal()
        self.submitted = []

    def submit(self, spec) -> bool:
        self.submitted.append(spec)
        return True


class FakeFacade:
    def reserve(self, request) -> None:  # pragma: no cover - not called in this test
        raise AssertionError("should not be called")


def make_query() -> BoardQuery:
    return BoardQuery(
        profile_name="default",
        venue_site_id=57,
        date="2026-03-22",
        start_time="18:00",
        slot_count=2,
    )


def test_request_reserve_returns_none_when_single_flight_rejects() -> None:
    controller = UiController(FakeFacade(), runner=RejectingRunner())

    generation = controller.request_reserve(
        ReserveRequest(
            profile_name="default",
            venue_site_id=57,
            date="2026-03-22",
            space_id=101,
            start_time="18:00",
            slot_count=2,
        )
    )

    assert generation is None


def test_request_start_polling_marks_poll_generation() -> None:
    controller = UiController(FakeFacade(), runner=RecordingRunner())

    generation = controller.request_start_polling(make_query())

    assert generation == 1
    assert controller.polling_state.status is PollingStatus.STARTING


def test_request_stop_polling_marks_stopping_state() -> None:
    controller = UiController(FakeFacade(), runner=RecordingRunner())
    controller.request_start_polling(make_query())

    generation = controller.request_stop_polling()

    assert generation == 2
    assert controller.polling_state.status is PollingStatus.STOPPING


def test_request_start_polling_returns_none_when_already_running() -> None:
    controller = UiController(FakeFacade(), runner=RecordingRunner())
    controller.request_start_polling(make_query())
    controller.set_polling_running()

    generation = controller.request_start_polling(make_query())

    assert generation is None
