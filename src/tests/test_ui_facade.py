from __future__ import annotations

from pathlib import Path

from src.auth.models import AuthBootstrapResult, ServiceAuthState
from src.config.profiles import ProfileSummary
from src.core.payment_service import PaymentTargetResult
from src.core.reservation_service import ReservationResult
from src.core.workflow import FullReservationResult
from src.parsers.cashier import (CashierTransactionParsed,
                                 CashierUrlParsed)
from src.parsers.catalog import CatalogParsed, SiteItem
from src.parsers.day_info import (Buddy, DayInfoParsed, OrderParamView,
                                  SiteParam, SlotState, SpaceSchedule,
                                  TimeSlot)
from src.parsers.order import SubmitParsed
from src.parsers.slot_filter import SlotChoice, SlotSolution
from src.ui.facade import BoardQuery, ReserveRequest, UiFacade
from src.ui.state import BoardStatus, SessionStatus


class FakeProfileManager:
    def __init__(self) -> None:
        self.last_modify = None

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

    def modify_profile(self, name: str, *, updates, unset_keys):
        self.last_modify = (name, dict(updates), list(unset_keys))


class FakeAuthManager:
    def __init__(self) -> None:
        self.logged_in = None
        self.persist_to_env = None
        self.sso_settings = type("SsoSettingsStub", (), {"persist_to_env": True})()

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

    def login_with_credentials(self, username: str, password: str):
        self.logged_in = (username, password)
        self.persist_to_env = self.sso_settings.persist_to_env
        return self.get_cgyy_auth_status()


class FakeWorkflow:
    def __init__(self, parsed: DayInfoParsed, solutions: list[SlotSolution] | None = None) -> None:
        self.parsed = parsed
        self.solutions = list(solutions or [])
        self.last_query = None
        self.last_solution_reservation = None

    def get_solutions(self, query):
        self.last_query = query
        return self.parsed, "2026-03-22", list(self.solutions)

    def run_solution_reservation(self, *, search_date: str, solution: SlotSolution):
        self.last_solution_reservation = (search_date, solution)
        return FullReservationResult(
            captcha=type("CaptchaResultStub", (), {"success": True, "message": "OK"})(),
            reservation=ReservationResult(
                success=True,
                message="OK",
                raw={},
                submit_parsed=SubmitParsed(
                    order_id=456,
                    trade_no="D123",
                    reservation_start_date="2026-04-01 18:00",
                    reservation_end_date="2026-04-01 19:00",
                ),
            ),
            solutions=[solution],
            site_param=self.parsed.site_param,
            reservation_date=search_date,
        )


class FakePaymentService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def create_reservation_payment(self, venue_trade_no: str) -> PaymentTargetResult:
        self.calls.append(venue_trade_no)
        return PaymentTargetResult(
            mode="mobile",
            resolved_target="weixin://wap/pay?prepayid=123",
            school_pay_url="https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
            pay_way_name="wxpay_wap",
            cashier=CashierUrlParsed(
                origin="https://cashier.cc-pay.cn",
                cashier_id="abc123",
                channel="BUAASSO",
            ),
            transaction=CashierTransactionParsed(
                transaction_id="txn-1",
                goods_id="goods-1",
                money=70.0,
                status="wait_payer_pay",
                subject="羽毛球",
                body="综合馆",
                target_order_id="760907",
                notify_url="https://notify.example",
                return_url="https://return.example",
            ),
        )


class FakeCatalogService:
    def get_catalog_parsed(self):
        return True, "ok", CatalogParsed(
            sports=[],
            sites=[
                SiteItem(site_id=57, site_name="羽毛球", venue_name="2号馆", campus_name="学院路"),
                SiteItem(site_id=58, site_name="乒乓球", venue_name="3号馆", campus_name="学院路"),
            ],
        )


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
        order_param_view=OrderParamView(
            phone="13900000000",
            buddy_list=[Buddy(id=1, name="Alice", user_id=1001)],
        ),
        site_param=SiteParam(
            site_name="羽毛球",
            venue_name="2号馆",
            campus_name="学院路",
            venue_site_id=57,
        ),
    )
    workflow = FakeWorkflow(
        parsed,
        solutions=[
            SlotSolution(
                choices=[
                    SlotChoice(
                        space_id=101,
                        time_id=1,
                        space_name="A1",
                        start_time="18:00",
                        end_time="18:30",
                        order_fee=25.0),
                    SlotChoice(
                        space_id=101,
                        time_id=2,
                        space_name="A1",
                        start_time="18:30",
                        end_time="19:00",
                        order_fee=25.0),
                ],
                total_fee=50.0,
                slot_count=2,
                total_hours=1.0,
            )
        ],
    )
    facade = UiFacade(
        profile_manager=FakeProfileManager(),
        auth_manager_factory=lambda profile_name: FakeAuthManager(),
        workflow_factory=lambda profile_name, query: workflow,
        catalog_service_factory=lambda profile_name: FakeCatalogService(),
    )

    profiles = facade.list_profiles()
    session = facade.get_session_state("default")
    catalog = facade.load_catalog("default")
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
    assert catalog.items[0].venue_site_id == 57
    assert catalog.items[0].campus_name == "学院路"
    assert board.status is BoardStatus.READY
    assert board.rows[0].cells[0].selectable is True
    assert board.rows[0].cells[1].selectable is True
    assert board.rows[0].cells[0].reservation_status == 1
    assert board.rows[0].cells[1].reservation_status == 1
    assert board.rows[0].cells[1].range_blocked is False
    assert board.rows[0].cells[2].reservation_status == 4
    assert len(board.solutions) == 1
    assert board.venue_label == "2号馆 / 羽毛球"
    assert board.available_dates == ["2026-03-22"]
    assert board.runtime_phone == "13900000000"
    assert [item.id for item in board.available_buddies] == ["1"]
    assert [item.name for item in board.available_buddies] == ["Alice"]
    assert workflow.last_query is not None and workflow.last_query.show_order_param is True
    assert workflow.last_query.start_time == "18:00"


def test_ui_facade_login_persists_auth_and_clears_legacy_sso_fields(tmp_path: Path) -> None:
    profile_manager = FakeProfileManager()
    auth_manager = FakeAuthManager()
    facade = UiFacade(
        root=tmp_path,
        profile_manager=profile_manager,
        auth_manager_factory=lambda profile_name: auth_manager,
        workflow_factory=lambda profile_name, query: FakeWorkflow(
            DayInfoParsed([], [], {}, None, None)
        ),
        catalog_service_factory=lambda profile_name: FakeCatalogService(),
    )

    session = facade.login(
        "default",
        "alice",
        "secret",
        persist_auth=True,
    )

    assert session.status is SessionStatus.AUTHENTICATED
    assert auth_manager.logged_in == ("alice", "secret")
    assert auth_manager.persist_to_env is True
    assert profile_manager.last_modify == (
        "default",
        {
            "CGYY_SSO_ENABLED": "0",
            "CGYY_SSO_PASSWORD": "",
            "CGYY_SSO_USERNAME": "",
        },
        [],
    )
    assert (tmp_path / ".env.profiles" / ".gui_cred_key").exists()


def test_ui_facade_login_session_only_clears_persisted_auth_fields() -> None:
    profile_manager = FakeProfileManager()
    auth_manager = FakeAuthManager()
    facade = UiFacade(
        profile_manager=profile_manager,
        auth_manager_factory=lambda profile_name: auth_manager,
        workflow_factory=lambda profile_name, query: FakeWorkflow(
            DayInfoParsed([], [], {}, None, None)
        ),
        catalog_service_factory=lambda profile_name: FakeCatalogService(),
    )

    session = facade.login(
        "default",
        "alice",
        "secret",
        persist_auth=False,
    )

    assert session.status is SessionStatus.AUTHENTICATED
    assert auth_manager.persist_to_env is False
    assert profile_manager.last_modify == (
        "default",
        {
            "CGYY_SSO_ENABLED": "0",
            "CGYY_SSO_USERNAME": "",
            "CGYY_SSO_PASSWORD": "",
            "CGYY_COOKIE": "",
            "CGYY_CG_AUTH": "",
        },
        [],
    )


def test_save_profile_patch_takes_effect_without_restart(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "CGYY_DISPLAY_NAME=Old Name",
                "CGYY_PHONE=13000000000",
                "CGYY_BUDDY_IDS=1",
                "CGYY_SELECTION_STRATEGY=same_first_digit",
                "CGYY_VENUE_SITE_ID=57",
                "CGYY_DEFAULT_SEARCH_DATE=2026-03-22",
                "CGYY_RESERVATION_START_TIME=18:00",
                "CGYY_RESERVATION_SLOT_COUNT=2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    facade = UiFacade(
        root=tmp_path,
        auth_manager_factory=lambda profile_name: FakeAuthManager(),
        workflow_factory=lambda profile_name, query: FakeWorkflow(
            DayInfoParsed([], [], {}, None, None)
        ),
        catalog_service_factory=lambda profile_name: FakeCatalogService(),
    )

    initial = facade.load_profile_form("default")
    assert initial.phone == "13000000000"
    assert initial.selection_strategy == "same_first_digit"

    saved = facade.save_profile_patch(
        initial.__class__(
            profile_name="default",
            display_name="New Name",
            phone="13900000000",
            buddy_ids="1,2",
            selection_strategy="same_first_digit,same_venue,cheapest",
            venue_site_id=58,
            default_search_date="2026-03-25",
            start_time="19:00",
            slot_count=3,
        )
    )
    reloaded = facade.load_profile_form("default")

    assert saved.display_name == "New Name"
    assert saved.phone == "13900000000"
    assert saved.buddy_ids == "1,2"
    assert saved.selection_strategy == "same_first_digit,same_venue,cheapest"
    assert saved.venue_site_id == 58
    assert saved.default_search_date == "2026-03-25"
    assert saved.start_time == "19:00"
    assert saved.slot_count == 3
    assert reloaded == saved


def test_ui_facade_reserve_auto_resolves_payment_target() -> None:
    parsed = DayInfoParsed(
        reservation_date_list=["2026-03-22"],
        time_slots=[],
        space_schedules_by_date={},
        order_param_view=None,
        site_param=SiteParam(
            site_name="羽毛球",
            venue_name="2号馆",
            campus_name="学院路",
            venue_site_id=57,
        ),
    )
    workflow = FakeWorkflow(parsed)
    payment_service = FakePaymentService()
    solution = SlotSolution(
        choices=[
            SlotChoice(
                space_id=101,
                time_id=1,
                space_name="A1",
                start_time="18:00",
                end_time="18:30",
                order_fee=25.0,
            )
        ],
        total_fee=25.0,
        slot_count=1,
        total_hours=0.5,
    )
    facade = UiFacade(
        profile_manager=FakeProfileManager(),
        auth_manager_factory=lambda profile_name: FakeAuthManager(),
        workflow_factory=lambda profile_name, query: workflow,
        payment_service_factory=lambda profile_name, query: payment_service,
        catalog_service_factory=lambda profile_name: FakeCatalogService(),
    )

    outcome = facade.reserve(
        ReserveRequest(
            profile_name="default",
            venue_site_id=57,
            date="2026-04-01",
            solution=solution,
            display_name="默认用户",
        )
    )

    assert outcome.success is True
    assert outcome.trade_no == "D123"
    assert outcome.payment_target == "weixin://wap/pay?prepayid=123"
    assert payment_service.calls == ["D123"]
