from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field

from src.cli.handlers.reservation import run_reserve
from src.core.payment_service import PaymentTargetResult
from src.core.reservation_service import ReservationResult
from src.core.workflow import FullReservationResult
from src.parsers.cashier import (CashierTransactionParsed,
                                 CashierUrlParsed)
from src.parsers.day_info import SiteParam
from src.parsers.order import SubmitParsed
from src.parsers.slot_filter import SlotChoice, SlotSolution


@dataclass
class _FakeCaptchaResult:
    success: bool = True
    message: str = "OK"


@dataclass
class _FakeUserSettings:
    profile_name: str = "alice"
    display_name: str = "Alice"


@dataclass
class _FakeApiSettings:
    default_search_date: str = "2026-04-01"


@dataclass
class _FakeWorkflow:
    user_settings: _FakeUserSettings = field(default_factory=_FakeUserSettings)
    api_settings: _FakeApiSettings = field(default_factory=_FakeApiSettings)

    def run_full_reservation(self) -> FullReservationResult:
        return FullReservationResult(
            captcha=_FakeCaptchaResult(),
            reservation=ReservationResult(
                success=True,
                message="OK",
                raw={},
                submit_parsed=SubmitParsed(
                    order_id=100,
                    trade_no="D100",
                    reservation_start_date="2026-04-01 18:00",
                    reservation_end_date="2026-04-01 19:00",
                ),
            ),
            solutions=[
                SlotSolution(
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
            ],
            site_param=SiteParam(
                site_name="羽毛球",
                venue_name="2号馆",
                campus_name="学院路",
                venue_site_id=57,
            ),
            reservation_date="2026-04-01",
        )


class _FakePaymentService:
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
                money=25.0,
                status="wait_payer_pay",
                subject="羽毛球",
                body="综合馆",
                target_order_id="760907",
                notify_url="https://notify.example",
                return_url="https://return.example",
            ),
        )


def test_run_reserve_auto_generates_payment_and_sends_notification(capsys, monkeypatch) -> None:
    workflow = _FakeWorkflow()
    payment_service = _FakePaymentService()
    sent = []

    monkeypatch.setattr(
        "src.cli.handlers.reservation.send_notification",
        lambda title, message, **kwargs: sent.append((title, message, kwargs)) or ["ios"],
    )

    run_reserve(
        workflow,
        payment_service,
        Namespace(),
        environ={"CGYY_PROFILE": "alice"},
    )

    out = capsys.readouterr().out
    assert "提交订单" in out
    assert "微信跳转 weixin://wap/pay?prepayid=123" in out
    assert payment_service.calls == ["D100"]
    assert sent == [
        (
            "CGYY 预约成功",
            "✅ [成功] 提交订单：OK\n"
            "   📌 订单ID 100 | 编号 D100\n"
            "   🕐 预约时间 2026-04-01 18:00 ~ 2026-04-01 19:00\n"
            "   👤 预定人 Alice | profile alice\n"
            "🎯 微信支付跳转 weixin://wap/pay?prepayid=123",
            {
                "url": "weixin://wap/pay?prepayid=123",
                "profile_name": "alice",
                "environ": {"CGYY_PROFILE": "alice"},
            },
        )
    ]
