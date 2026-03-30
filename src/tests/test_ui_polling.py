from __future__ import annotations

from PySide6.QtWidgets import QApplication

from src.ui.facade import BoardQuery
from src.ui.polling import PollingCoordinator
from src.ui.state import PollingStatus


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _pump_events(iterations: int = 40) -> None:
    app = _app()
    for _ in range(iterations):
        app.processEvents()


def make_query() -> BoardQuery:
    return BoardQuery(
        profile_name="default",
        venue_site_id=57,
        date="2026-03-22",
        start_time="18:00",
        slot_count=2,
    )


def test_polling_coordinator_emits_query_tick_and_updates_summary() -> None:
    _app()
    fired: list[BoardQuery] = []
    states = []

    coordinator = PollingCoordinator(
        on_tick=lambda query: fired.append(query),
        interval_sec=1,
    )
    coordinator.state_changed.connect(states.append)

    coordinator.start(make_query())
    coordinator._on_timeout_for_test()
    coordinator.stop()

    assert fired
    assert states[0].status is PollingStatus.STARTING
    assert any(state.status is PollingStatus.RUNNING for state in states)
    assert states[-1].status is PollingStatus.STOPPED


def test_polling_coordinator_start_stop_are_idempotent() -> None:
    _app()
    coordinator = PollingCoordinator(
        on_tick=lambda query: None,
        interval_sec=1,
    )

    assert coordinator.start(make_query()) is True
    assert coordinator.start(make_query()) is False
    assert coordinator.stop() is True
    assert coordinator.stop() is False
