from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from src.api.cashier_api import CashierApi
from src.api.cashier_client import CashierClient
from src.api.reservation_api import ReservationApi
from src.auth.cashier_auth_service import CashierBootstrapService
from src.core.exceptions import PaymentError
from src.parsers.cashier import (CashierTransactionParsed, CashierUrlParsed,
                                 choose_pay_way, extract_weixin_scheme,
                                 parse_cashier_pay_response,
                                 parse_cashier_pay_ways_response,
                                 parse_cashier_transaction_response,
                                 parse_cashier_url)
from src.parsers.order import OrderPayParsed, parse_order_pay_response

PaymentMode = Literal["desktop", "mobile"]
DEFAULT_RESERVATION_PAYMENT_MODE: PaymentMode = "mobile"
DEFAULT_RESERVATION_PAY_WAY_NAME = "wxpay_wap"


@dataclass
class OrderPaymentResult:
    success: bool
    message: str
    raw: Dict[str, Any]
    order_pay_parsed: Optional[OrderPayParsed] = None


@dataclass
class PaymentTargetResult:
    mode: PaymentMode
    resolved_target: str
    school_pay_url: str
    pay_way_name: str = ""
    cashier: Optional[CashierUrlParsed] = None
    transaction: Optional[CashierTransactionParsed] = None


@dataclass
class OrderPaymentFlowResult:
    order_payment: OrderPaymentResult
    payment_result: PaymentTargetResult


class PaymentService:
    def __init__(
        self,
        reservation_api: ReservationApi,
        cashier_bootstrap_service: CashierBootstrapService,
        *,
        cashier_timeout_sec: float = 15.0,
        retry_count: int = 3,
        retry_interval_sec: float = 2.0,
    ) -> None:
        self.reservation_api = reservation_api
        self.cashier_bootstrap_service = cashier_bootstrap_service
        self.cashier_timeout_sec = cashier_timeout_sec
        self.retry_count = retry_count
        self.retry_interval_sec = retry_interval_sec

    def _bootstrap_seed_cookie(self) -> str:
        client = getattr(self.reservation_api, "client", None)
        auth_settings = getattr(client, "auth_settings", None)
        cookie = getattr(auth_settings, "cookie", "")
        return str(cookie or "")

    def _build_cashier_api(self, cashier_origin: str, cookie_header: str) -> CashierApi:
        client = CashierClient(
            base_url=cashier_origin,
            cookie=cookie_header,
            timeout_sec=self.cashier_timeout_sec,
            retry_count=self.retry_count,
            retry_interval_sec=self.retry_interval_sec,
        )
        return CashierApi(client=client)

    def create_order_payment(
        self,
        venue_trade_no: str,
        *,
        pay_type: int = 13,
        is_app: int = 0,
    ) -> OrderPaymentResult:
        raw = self.reservation_api.create_order_payment(
            venue_trade_no,
            pay_type=pay_type,
            is_app=is_app,
        )
        success, message, parsed = parse_order_pay_response(raw)
        return OrderPaymentResult(
            success=success,
            message=message,
            raw=raw,
            order_pay_parsed=parsed,
        )

    def resolve_mobile_payment(
        self,
        cashier_url: str,
        *,
        pay_way_name: str | None = None,
    ) -> PaymentTargetResult:
        cashier = parse_cashier_url(cashier_url)
        if not cashier:
            raise PaymentError("cashier URL 缺少 id 参数")

        auth_state = self.cashier_bootstrap_service.bootstrap_from_school_pay_url(
            cashier_url,
            cookie_header=self._bootstrap_seed_cookie(),
        )
        effective_cookie = auth_state.cookie
        if not effective_cookie:
            raise PaymentError("cashier 支付缺少可用 cookie")

        cashier_api = self._build_cashier_api(cashier.origin, effective_cookie)

        transaction_raw = cashier_api.get_transaction(cashier.cashier_id, cashier_url)
        ok, message, transaction = parse_cashier_transaction_response(transaction_raw)
        if not ok or not transaction:
            raise PaymentError(f"cashier 交易查询失败：{message}")

        selected_pay_way_name = pay_way_name or DEFAULT_RESERVATION_PAY_WAY_NAME
        pay_scene = "wap"
        pay_ways_raw = cashier_api.get_pay_ways(transaction.goods_id, pay_scene, cashier_url)
        ok, message, pay_ways = parse_cashier_pay_ways_response(pay_ways_raw)
        if not ok or not pay_ways:
            raise PaymentError(f"cashier 支付方式查询失败：{message}")

        pay_way = choose_pay_way(pay_ways, selected_pay_way_name)
        if not pay_way:
            available = ",".join(item.name for item in pay_ways.normal)
            raise PaymentError(
                f"未找到支付方式 {selected_pay_way_name}，可用支付方式：{available}"
            )

        pay_raw = cashier_api.pay(cashier.cashier_id, pay_way.id, cashier_url)
        ok, message, pay_result = parse_cashier_pay_response(pay_raw)
        if not ok or not pay_result:
            raise PaymentError(f"cashier 拉起支付失败：{message}")

        if not pay_result.pay_url:
            raise PaymentError("mobile 模式未返回 payUrl")
        html = cashier_api.fetch_wap_page(
            pay_result.pay_url,
            cashier_origin=cashier.origin,
            cashier_id=cashier.cashier_id,
            referer=cashier_url,
        )
        resolved_target = extract_weixin_scheme(html)
        if not resolved_target:
            raise PaymentError("未在 checkmweb 页面中解析出 weixin deeplink")

        return PaymentTargetResult(
            mode="mobile",
            resolved_target=resolved_target,
            school_pay_url=cashier_url,
            pay_way_name=pay_way.name,
            cashier=cashier,
            transaction=transaction,
        )

    def create_and_resolve_order_payment(
        self,
        venue_trade_no: str,
        *,
        mode: PaymentMode = "desktop",
        pay_type: int = 13,
        is_app: int = 0,
        pay_way_name: str | None = None,
    ) -> OrderPaymentFlowResult:
        order_payment = self.create_order_payment(
            venue_trade_no,
            pay_type=pay_type,
            is_app=is_app,
        )
        if not order_payment.success or not order_payment.order_pay_parsed:
            raise PaymentError(f"订单支付初始化失败：{order_payment.message}")

        school_pay_url = order_payment.order_pay_parsed.school_pay_url
        if mode == "desktop":
            payment_result = PaymentTargetResult(
                mode="desktop",
                resolved_target=school_pay_url,
                school_pay_url=school_pay_url,
            )
        else:
            payment_result = self.resolve_mobile_payment(
                school_pay_url,
                pay_way_name=pay_way_name,
            )
        return OrderPaymentFlowResult(
            order_payment=order_payment,
            payment_result=payment_result,
        )

    def create_reservation_payment(
        self,
        venue_trade_no: str,
        *,
        pay_way_name: str = DEFAULT_RESERVATION_PAY_WAY_NAME,
    ) -> PaymentTargetResult:
        return self.create_and_resolve_order_payment(
            venue_trade_no,
            mode=DEFAULT_RESERVATION_PAYMENT_MODE,
            pay_way_name=pay_way_name,
        ).payment_result
