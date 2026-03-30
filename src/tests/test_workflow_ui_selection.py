from __future__ import annotations

import json

import pytest

from src.config.settings import ApiSettings, UserSettings
from src.core.captcha_service import (CaptchaData, CaptchaVerification,
                                      CaptchaVerificationResult)
from src.core.exceptions import BuddyConfigError
from src.core.reservation_service import ReservationResult
from src.core.workflow import ReservationWorkflow
from src.parsers.day_info import (Buddy, DayInfoParsed, OrderParamView, SiteParam,
                                  SlotState, SpaceSchedule, TimeSlot)
from src.parsers.order import SubmitParsed


class FakeCaptchaService:
    def fetch_captcha(self) -> CaptchaData:
        return CaptchaData(
            secret_key="secret",
            token="token",
            word_list=["A"],
            image_path="captcha.png",  # type: ignore[arg-type]
        )

    def verify_captcha(self, captcha_data: CaptchaData) -> CaptchaVerificationResult:
        return CaptchaVerificationResult(
            success=True,
            message="ok",
            verification=CaptchaVerification(point_json="point", verify_json="verify"),
        )


class FakeReservationService:
    def __init__(self, info: DayInfoParsed) -> None:
        self.info = info
        self.last_submit_kwargs: dict | None = None

    def get_info_parsed(self, search_date: str | None = None, has_reserve_info: bool = False):
        return True, "", self.info

    def submit_reservation(self, captcha_token: str, captcha_verification: str, **kwargs):
        self.last_submit_kwargs = {
            "captcha_token": captcha_token,
            "captcha_verification": captcha_verification,
            **kwargs,
        }
        return ReservationResult(
            success=True,
            message="ok",
            raw={},
            submit_parsed=SubmitParsed(
                order_id=100,
                trade_no="T-100",
                reservation_start_date="2026-03-22 18:00",
                reservation_end_date="2026-03-22 19:00",
            ),
        )


def test_run_selected_reservation_uses_explicit_space_and_time_range() -> None:
    info = DayInfoParsed(
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
                ),
                SpaceSchedule(
                    space_id=102,
                    space_name="A2",
                    venue_site_id=57,
                    slots={
                        "1": SlotState(1, True, order_fee=30.0),
                        "2": SlotState(1, True, order_fee=30.0),
                        "3": SlotState(1, True, order_fee=30.0),
                    },
                ),
            ]
        },
        order_param_view=None,
        site_param=SiteParam(
            site_name="羽毛球",
            venue_name="2号馆",
            campus_name="学院路",
            venue_site_id=57,
            buddy_num_min=0,
            buddy_num_max=0,
        ),
    )
    reservation_service = FakeReservationService(info)
    workflow = ReservationWorkflow(
        captcha_service=FakeCaptchaService(),
        reservation_service=reservation_service,  # type: ignore[arg-type]
        delay_min=0.0,
        delay_max=0.0,
        api_settings=ApiSettings(default_search_date="2026-03-22", venue_site_id=57),
        user_settings=UserSettings(profile_name="default", reservation_slot_count=2),
    )

    result = workflow.run_selected_reservation(
        search_date="2026-03-22",
        space_id=101,
        start_time="18:00",
        slot_count=2,
    )

    assert result.reservation.success is True
    assert reservation_service.last_submit_kwargs is not None
    assert reservation_service.last_submit_kwargs["reservation_date"] == "2026-03-22"
    assert reservation_service.last_submit_kwargs["order_price"] == 50
    selected = json.loads(reservation_service.last_submit_kwargs["reservation_order_json"])
    assert selected == [
        {"spaceId": "101", "timeId": "1"},
        {"spaceId": "101", "timeId": "2"},
    ]


def test_run_selected_reservation_preserves_buddy_ids_within_buddy_max() -> None:
    info = DayInfoParsed(
        reservation_date_list=["2026-03-22"],
        time_slots=[
            TimeSlot(id=1, begin_time="18:00", end_time="18:30"),
            TimeSlot(id=2, begin_time="18:30", end_time="19:00"),
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
                    },
                ),
            ]
        },
        order_param_view=OrderParamView(
            phone="13900000000",
            buddy_list=[
                Buddy(id=1, name="Alice", user_id=1001),
                Buddy(id=2, name="Bob", user_id=1002),
                Buddy(id=3, name="Carol", user_id=1003),
            ],
        ),
        site_param=SiteParam(
            site_name="羽毛球",
            venue_name="2号馆",
            campus_name="学院路",
            venue_site_id=57,
            buddy_num_min=1,
            buddy_num_max=3,
        ),
    )
    reservation_service = FakeReservationService(info)
    workflow = ReservationWorkflow(
        captcha_service=FakeCaptchaService(),
        reservation_service=reservation_service,  # type: ignore[arg-type]
        delay_min=0.0,
        delay_max=0.0,
        api_settings=ApiSettings(default_search_date="2026-03-22", venue_site_id=57),
        user_settings=UserSettings(
            profile_name="default",
            reservation_slot_count=2,
            buddy_ids="1,2",
        ),
    )

    workflow.run_selected_reservation(
        search_date="2026-03-22",
        space_id=101,
        start_time="18:00",
        slot_count=2,
    )

    assert reservation_service.last_submit_kwargs is not None
    assert reservation_service.last_submit_kwargs["buddy_ids"] == "1,2"


def test_run_selected_reservation_truncates_buddy_ids_to_buddy_max() -> None:
    info = DayInfoParsed(
        reservation_date_list=["2026-03-22"],
        time_slots=[
            TimeSlot(id=1, begin_time="18:00", end_time="18:30"),
            TimeSlot(id=2, begin_time="18:30", end_time="19:00"),
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
                    },
                ),
            ]
        },
        order_param_view=OrderParamView(
            phone="13900000000",
            buddy_list=[
                Buddy(id=1, name="Alice", user_id=1001),
                Buddy(id=2, name="Bob", user_id=1002),
                Buddy(id=3, name="Carol", user_id=1003),
            ],
        ),
        site_param=SiteParam(
            site_name="羽毛球",
            venue_name="2号馆",
            campus_name="学院路",
            venue_site_id=57,
            buddy_num_min=1,
            buddy_num_max=2,
        ),
    )
    reservation_service = FakeReservationService(info)
    workflow = ReservationWorkflow(
        captcha_service=FakeCaptchaService(),
        reservation_service=reservation_service,  # type: ignore[arg-type]
        delay_min=0.0,
        delay_max=0.0,
        api_settings=ApiSettings(default_search_date="2026-03-22", venue_site_id=57),
        user_settings=UserSettings(
            profile_name="default",
            reservation_slot_count=2,
            buddy_ids="1,2,3",
        ),
    )

    workflow.run_selected_reservation(
        search_date="2026-03-22",
        space_id=101,
        start_time="18:00",
        slot_count=2,
    )

    assert reservation_service.last_submit_kwargs is not None
    assert reservation_service.last_submit_kwargs["buddy_ids"] == "1,2"


def test_run_selected_reservation_rejects_buddy_ids_below_buddy_min() -> None:
    info = DayInfoParsed(
        reservation_date_list=["2026-03-22"],
        time_slots=[
            TimeSlot(id=1, begin_time="18:00", end_time="18:30"),
            TimeSlot(id=2, begin_time="18:30", end_time="19:00"),
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
                    },
                ),
            ]
        },
        order_param_view=OrderParamView(
            phone="13900000000",
            buddy_list=[
                Buddy(id=1, name="Alice", user_id=1001),
                Buddy(id=2, name="Bob", user_id=1002),
            ],
        ),
        site_param=SiteParam(
            site_name="羽毛球",
            venue_name="2号馆",
            campus_name="学院路",
            venue_site_id=57,
            buddy_num_min=2,
            buddy_num_max=3,
        ),
    )
    reservation_service = FakeReservationService(info)
    workflow = ReservationWorkflow(
        captcha_service=FakeCaptchaService(),
        reservation_service=reservation_service,  # type: ignore[arg-type]
        delay_min=0.0,
        delay_max=0.0,
        api_settings=ApiSettings(default_search_date="2026-03-22", venue_site_id=57),
        user_settings=UserSettings(
            profile_name="default",
            reservation_slot_count=2,
            buddy_ids="1",
        ),
    )

    with pytest.raises(BuddyConfigError):
        workflow.run_selected_reservation(
            search_date="2026-03-22",
            space_id=101,
            start_time="18:00",
            slot_count=2,
        )
