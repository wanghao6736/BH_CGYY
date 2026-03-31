from __future__ import annotations

import pytest

from src.auth.cashier_auth_service import CashierBootstrapService
from src.auth.models import ServiceAuthState
from src.core.exceptions import PaymentError
from src.core.payment_service import PaymentService


class _FakeReservationApi:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {
            "code": 200,
            "data": {
                "schoolPayUrl": "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
            },
        }
        self.calls: list[tuple[str, int, int]] = []

    def create_order_payment(self, venue_trade_no: str, pay_type: int = 13, is_app: int = 0) -> dict:
        self.calls.append((venue_trade_no, pay_type, is_app))
        return self.response


class _FakeCashierApi:
    def __init__(
        self,
        *,
        transaction_response: dict | None = None,
        pay_ways_response: dict | None = None,
        pay_response: dict | None = None,
        wap_html: str = "",
    ) -> None:
        self.transaction_response = transaction_response or {
            "success": True,
            "data": {
                "id": "txn-1",
                "goodsId": "goods-1",
                "money": 70,
                "status": 1,
                "subject": "羽毛球",
                "body": "综合馆",
                "targetOrderId": "760907",
                "notifyUrl": "https://notify.example",
                "returnUrl": "https://return.example",
            },
        }
        self.pay_ways_response = pay_ways_response or {
            "success": True,
            "data": {
                "normal": [
                    {"id": "way-desktop", "name": "wxpay_web", "text": "桌面支付", "description": ""},
                    {"id": "way-mobile", "name": "wxpay_wap", "text": "移动支付", "description": ""},
                ]
            },
        }
        self.pay_response = pay_response or {
            "success": True,
            "data": {
                "transactionId": "txn-1",
                "isPaid": False,
                "payUrl": "https://wx.tenpay.com/checkmweb?prepay_id=abc",
                "payQrCode": "weixin://wxpay/bizpayurl?pr=desktop",
                "payWebForm": "",
                "wxpayJsapiDataStr": "",
            },
        }
        self.wap_html = wap_html or '<a href="weixin://wap/pay?prepayid=12345">Pay</a>'
        self.calls: list[tuple[str, tuple]] = []

    def get_transaction(self, cashier_id: str, referer: str) -> dict:
        self.calls.append(("get_transaction", (cashier_id, referer)))
        return self.transaction_response

    def get_pay_ways(self, goods_id: str, pay_scene: str, referer: str) -> dict:
        self.calls.append(("get_pay_ways", (goods_id, pay_scene, referer)))
        return self.pay_ways_response

    def pay(
        self,
        cashier_id: str,
        pay_way_id: str,
        referer: str,
        phone_number: str = "",
        ec_code: str = "",
    ) -> dict:
        self.calls.append(("pay", (cashier_id, pay_way_id, referer, phone_number, ec_code)))
        return self.pay_response

    @staticmethod
    def build_wap_request_url(pay_url: str, cashier_origin: str, cashier_id: str) -> str:
        return (
            f"{pay_url}&redirect_url="
            f"https%3A%2F%2Fcashier.cc-pay.cn%2Fcashier%3Fid%3D{cashier_id}%26for%3Dwxpay_wap"
        )

    def fetch_wap_page(
        self,
        pay_url: str,
        *,
        cashier_origin: str,
        cashier_id: str,
        referer: str,
    ) -> str:
        self.calls.append(("fetch_wap_page", (pay_url, cashier_origin, cashier_id, referer)))
        return self.wap_html


class _FakeCashierBootstrapService(CashierBootstrapService):
    def __init__(self, state: ServiceAuthState | None = None) -> None:
        super().__init__()
        self.state = state or ServiceAuthState(
            service_name="cashier",
            cookie="connect.sid=sid-1; user_id=user-1",
            source="cashier",
        )
        self.calls: list[str] = []

    def bootstrap_from_school_pay_url(
        self,
        cashier_url: str,
        *,
        cookie_header: str = "",
    ) -> ServiceAuthState:
        self.calls.append(cashier_url)
        return self.state


class _TestPaymentService(PaymentService):
    def __init__(self, reservation_api, bootstrap_service, cashier_api) -> None:
        super().__init__(reservation_api, bootstrap_service)
        self._cashier_api = cashier_api
        self.cashier_api_inputs: list[tuple[str, str]] = []

    def _build_cashier_api(self, cashier_origin: str, cookie_header: str):
        self.cashier_api_inputs.append((cashier_origin, cookie_header))
        return self._cashier_api


def test_create_order_payment_uses_expected_default_args() -> None:
    reservation_api = _FakeReservationApi()
    service = PaymentService(
        reservation_api=reservation_api,  # type: ignore[arg-type]
        cashier_bootstrap_service=_FakeCashierBootstrapService(),
    )
    result = service.create_order_payment("D260331000575")
    assert result.success is True
    assert result.order_pay_parsed is not None
    assert result.order_pay_parsed.school_pay_url.endswith("id=abc123&channel=BUAASSO")
    assert reservation_api.calls == [("D260331000575", 13, 0)]


def test_create_and_resolve_order_payment_desktop_returns_school_pay_url() -> None:
    reservation_api = _FakeReservationApi()
    bootstrap_service = _FakeCashierBootstrapService()
    cashier_api = _FakeCashierApi()
    service = _TestPaymentService(reservation_api, bootstrap_service, cashier_api)

    result = service.create_and_resolve_order_payment("D260331000575", mode="desktop")

    assert bootstrap_service.calls == []
    assert service.cashier_api_inputs == []
    assert result.payment_result.mode == "desktop"
    assert result.payment_result.resolved_target == (
        "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO"
    )


def test_resolve_mobile_payment_extracts_scheme() -> None:
    reservation_api = _FakeReservationApi()
    bootstrap_service = _FakeCashierBootstrapService()
    cashier_api = _FakeCashierApi()
    service = _TestPaymentService(reservation_api, bootstrap_service, cashier_api)

    result = service.resolve_mobile_payment(
        "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
    )

    assert result.pay_way_name == "wxpay_wap"
    assert result.resolved_target == "weixin://wap/pay?prepayid=12345"


def test_resolve_mobile_payment_respects_custom_pay_way_name() -> None:
    reservation_api = _FakeReservationApi()
    bootstrap_service = _FakeCashierBootstrapService()
    cashier_api = _FakeCashierApi()
    service = _TestPaymentService(reservation_api, bootstrap_service, cashier_api)

    result = service.resolve_mobile_payment(
        "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
        pay_way_name="wxpay_wap",
    )

    assert result.mode == "mobile"
    assert result.pay_way_name == "wxpay_wap"
    assert result.resolved_target == "weixin://wap/pay?prepayid=12345"


def test_create_and_resolve_order_payment_combines_both_steps() -> None:
    reservation_api = _FakeReservationApi()
    bootstrap_service = _FakeCashierBootstrapService()
    cashier_api = _FakeCashierApi()
    service = _TestPaymentService(reservation_api, bootstrap_service, cashier_api)

    result = service.create_and_resolve_order_payment("D260331000575", mode="mobile")

    assert result.order_payment.order_pay_parsed is not None
    assert result.payment_result.transaction is not None
    assert result.payment_result.transaction.goods_id == "goods-1"
    assert result.payment_result.resolved_target.startswith("weixin://")


def test_create_reservation_payment_uses_mobile_wxpay_flow() -> None:
    reservation_api = _FakeReservationApi()
    bootstrap_service = _FakeCashierBootstrapService()
    cashier_api = _FakeCashierApi()
    service = _TestPaymentService(reservation_api, bootstrap_service, cashier_api)

    result = service.create_reservation_payment("D260331000575")

    assert result.mode == "mobile"
    assert result.pay_way_name == "wxpay_wap"
    assert result.resolved_target == "weixin://wap/pay?prepayid=12345"


def test_resolve_mobile_payment_raises_when_pay_way_missing() -> None:
    reservation_api = _FakeReservationApi()
    bootstrap_service = _FakeCashierBootstrapService()
    cashier_api = _FakeCashierApi(
        pay_ways_response={
            "success": True,
            "data": {
                "normal": [
                    {"id": "way-1", "name": "alipay", "text": "支付宝", "description": ""},
                ]
            },
        }
    )
    service = _TestPaymentService(reservation_api, bootstrap_service, cashier_api)

    with pytest.raises(PaymentError, match="未找到支付方式"):
        service.resolve_mobile_payment(
            "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
        )


def test_create_and_resolve_order_payment_raises_when_school_pay_url_missing() -> None:
    reservation_api = _FakeReservationApi(response={"code": 200, "data": {}})
    service = PaymentService(
        reservation_api=reservation_api,  # type: ignore[arg-type]
        cashier_bootstrap_service=_FakeCashierBootstrapService(),
    )

    with pytest.raises(PaymentError, match="订单支付初始化失败"):
        service.create_and_resolve_order_payment("D260331000575")
