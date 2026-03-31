from src.core.payment_service import PaymentTargetResult
from src.parsers.cashier import (CashierTransactionParsed,
                                 CashierUrlParsed)
from src.parsers.order import SubmitParsed
from src.presenters.format import format_payment_result, format_submit_result


def test_format_submit_result_includes_display_name_and_profile() -> None:
    text = format_submit_result(
        True,
        "OK",
        SubmitParsed(
            order_id=1,
            trade_no="D1",
            reservation_start_date="2026-03-21 19:00",
            reservation_end_date="2026-03-21 20:00",
        ),
        display_name="Alice",
        profile_name="alice",
    )

    assert "预定人 Alice | profile alice" in text


def test_format_payment_result_includes_target_and_identity() -> None:
    text = format_payment_result(
        PaymentTargetResult(
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
        ),
        display_name="Alice",
        profile_name="alice",
    )

    assert "cashierId abc123" in text
    assert "weixin://wap/pay?prepayid=123" in text
    assert "当前身份 Alice | profile alice" in text
