from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field

from src.cli.context import AppServices, CommandContext
from src.cli.handlers.payment import run_pay
from src.core.payment_service import (OrderPaymentFlowResult,
                                      OrderPaymentResult)
from src.core.payment_service import PaymentTargetResult
from src.parsers.order import OrderPayParsed


@dataclass
class _FakeWorkflowUserSettings:
    profile_name: str = "alice"
    display_name: str = "Alice"


@dataclass
class _FakeWorkflow:
    user_settings: _FakeWorkflowUserSettings = field(default_factory=_FakeWorkflowUserSettings)


class _FakePaymentService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_and_resolve_order_payment(
        self,
        trade_no: str,
        *,
        mode: str,
        pay_way_name: str | None,
    ) -> OrderPaymentFlowResult:
        self.calls.append(
            {
                "trade_no": trade_no,
                "mode": mode,
                "pay_way_name": pay_way_name,
            }
        )
        return OrderPaymentFlowResult(
            order_payment=OrderPaymentResult(
                success=True,
                message="ok",
                raw={},
                order_pay_parsed=OrderPayParsed(
                    school_pay_url="https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO"
                ),
            ),
            payment_result=PaymentTargetResult(
                mode="desktop",
                resolved_target="https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
                school_pay_url="https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
            ),
        )


def test_run_pay_prints_payment_result_and_sends_notification(capsys, monkeypatch) -> None:
    service = _FakePaymentService()
    sent = []

    monkeypatch.setattr(
        "src.cli.handlers.payment.send_notification",
        lambda title, message, **kwargs: sent.append((title, message, kwargs)) or ["ios"],
    )

    run_pay(
        service,
        _FakeWorkflow(),
        Namespace(
            trade_no="D260331000575",
            mode="desktop",
            pay_way_name=None,
        ),
        environ={"CGYY_PROFILE": "alice"},
    )

    out = capsys.readouterr().out
    assert "订单支付" in out
    assert "schoolPayUrl https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO" in out
    assert "当前身份 Alice | profile alice" in out
    assert service.calls == [
        {
            "trade_no": "D260331000575",
            "mode": "desktop",
            "pay_way_name": None,
        }
    ]
    assert sent == [
        (
            "CGYY 支付页面已生成",
            "💳 支付模式 desktop\n"
            "🔗 schoolPayUrl https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO\n"
            "👤 当前身份 Alice | profile alice",
            {
                "url": "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
                "profile_name": "alice",
                "environ": {"CGYY_PROFILE": "alice"},
            },
        )
    ]


def test_handle_pay_uses_context_services(capsys, monkeypatch) -> None:
    from src.cli.handlers.payment import handle_pay

    service = _FakePaymentService()
    context = CommandContext(
        services=AppServices(
            workflow=_FakeWorkflow(),  # type: ignore[arg-type]
            payment_service=service,  # type: ignore[arg-type]
        ),
        auth_manager=object(),  # type: ignore[arg-type]
        profile_manager=object(),  # type: ignore[arg-type]
    )
    args = Namespace(
        trade_no="D260331000575",
        mode="desktop",
        pay_way_name="wxpay_web",
    )

    calls = []
    monkeypatch.setattr(
        "src.cli.handlers.payment.send_notification",
        lambda title, message, **kwargs: calls.append((title, message, kwargs)) or ["ios"],
    )

    handle_pay(context, args)

    out = capsys.readouterr().out
    assert "订单支付" in out
    assert service.calls[-1]["pay_way_name"] == "wxpay_web"
    assert calls[0][2]["profile_name"] == "alice"
