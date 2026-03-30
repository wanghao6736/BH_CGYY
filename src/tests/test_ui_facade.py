from __future__ import annotations

from src.auth.models import AuthBootstrapResult, ServiceAuthState
from src.config.profiles import ProfileSummary
from src.parsers.day_info import DayInfoParsed, SiteParam, SlotState, SpaceSchedule, TimeSlot
from src.ui.facade import BoardQuery, UiFacade
from src.ui.state import BoardStatus, SessionStatus


class FakeProfileManager:
    def list_profiles(self):
        return [
            ProfileSummary(
                name="default",
                path="default.env",  # type: ignore[arg-type]
                display_name="默认用户",
                auth_source="self",
                sso_source="self",
            )
        ]


class FakeAuthManager:
    def get_cgyy_auth_status(self):
        return AuthBootstrapResult(
            reused=True,
            refreshed=False,
            state=ServiceAuthState(
                service_name="cgyy",
                cookie="cookie",
                cg_authorization="auth",
                source="env",
            ),
        )


class FakeWorkflow:
    def __init__(self, parsed: DayInfoParsed) -> None:
        self.parsed = parsed

    def get_solutions(self, query):
        return self.parsed, "2026-03-22", []


def test_ui_facade_builds_profile_session_and_board_state() -> None:
    parsed = DayInfoParsed(
        reservation_date_list=["2026-03-22"],
        time_slots=[
            TimeSlot(id=1, begin_time="18:00", end_time="18:30"),
            TimeSlot(id=2, begin_time="18:30", end_time="19:00"),
            TimeSlot(id=3, begin_time="19:00", end_time="19:30"),
        ],
        space_schedules_by_date={
            "2026-03-22": [
                SpaceSchedule(
                    space_id=101,
                    space_name="A1",
                    venue_site_id=57,
                    slots={
                        "1": SlotState(1, True, order_fee=25.0),
                        "2": SlotState(1, True, order_fee=25.0),
                        "3": SlotState(4, False, order_fee=25.0),
                    },
                )
            ]
        },
        order_param_view=None,
        site_param=SiteParam(
            site_name="羽毛球",
            venue_name="2号馆",
            campus_name="学院路",
            venue_site_id=57,
        ),
    )
    facade = UiFacade(
        profile_manager=FakeProfileManager(),
        auth_manager_factory=lambda profile_name: FakeAuthManager(),
        workflow_factory=lambda profile_name, query: FakeWorkflow(parsed),
    )

    profiles = facade.list_profiles()
    session = facade.get_session_state("default")
    board = facade.load_board(
        BoardQuery(
            profile_name="default",
            venue_site_id=57,
            date="2026-03-22",
            start_time="18:00",
            slot_count=2,
        )
    )

    assert profiles[0].display_name == "默认用户"
    assert session.status is SessionStatus.AUTHENTICATED
    assert board.status is BoardStatus.READY
    assert board.rows[0].cells[0].selectable is True
    assert board.rows[0].cells[1].selectable is False
    assert board.venue_label == "2号馆 / 羽毛球"
