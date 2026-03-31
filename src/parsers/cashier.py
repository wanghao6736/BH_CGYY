"""Parse cashier URL, transaction, pay ways and pay result responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import parse_qs, urlsplit

from src.parsers.common import parse_success_message

WAP_DEEPLINK_RE = re.compile(r"(weixin://[^\"'<>]+)")


@dataclass
class CashierUrlParsed:
    origin: str
    cashier_id: str
    channel: str = ""


def parse_cashier_url(cashier_url: str) -> Optional[CashierUrlParsed]:
    parts = urlsplit(cashier_url)
    query = parse_qs(parts.query)
    cashier_id = query.get("id", [None])[0]
    if not cashier_id:
        return None
    channel = query.get("channel", [""])[0] or ""
    origin = f"{parts.scheme}://{parts.netloc}"
    return CashierUrlParsed(
        origin=origin,
        cashier_id=str(cashier_id),
        channel=str(channel),
    )


@dataclass
class CashierTransactionParsed:
    transaction_id: str
    goods_id: str
    money: float
    status: str
    subject: str
    body: str
    target_order_id: str
    notify_url: str
    return_url: str


def parse_cashier_transaction_data(data: dict) -> Optional[CashierTransactionParsed]:
    if not isinstance(data, dict):
        return None
    transaction_id = data.get("id")
    goods_id = data.get("goodsId")
    if transaction_id is None or goods_id is None:
        return None
    return CashierTransactionParsed(
        transaction_id=str(transaction_id),
        goods_id=str(goods_id),
        money=float(data.get("money") or 0),
        status=str(data.get("status") or ""),
        subject=str(data.get("subject") or ""),
        body=str(data.get("body") or ""),
        target_order_id=str(data.get("targetOrderId") or ""),
        notify_url=str(data.get("notifyUrl") or ""),
        return_url=str(data.get("returnUrl") or ""),
    )


def parse_cashier_transaction_response(
    resp: dict,
) -> tuple[bool, str, Optional[CashierTransactionParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_cashier_transaction_data(data) if success and data else None
    return success, message, parsed


@dataclass
class CashierPayWayItem:
    id: str
    name: str
    text: str
    description: str


@dataclass
class CashierPayWaysParsed:
    normal: List[CashierPayWayItem]


def _parse_pay_way_item(raw: dict) -> Optional[CashierPayWayItem]:
    if not isinstance(raw, dict):
        return None
    pay_way_id = raw.get("id")
    name = raw.get("name")
    if pay_way_id is None or not name:
        return None
    return CashierPayWayItem(
        id=str(pay_way_id),
        name=str(name),
        text=str(raw.get("text") or ""),
        description=str(raw.get("description") or ""),
    )


def parse_cashier_pay_ways_data(data: dict) -> Optional[CashierPayWaysParsed]:
    if not isinstance(data, dict):
        return None
    normal_items = data.get("normal") or []
    if not isinstance(normal_items, list):
        return CashierPayWaysParsed(normal=[])
    normal: List[CashierPayWayItem] = []
    for item in normal_items:
        parsed = _parse_pay_way_item(item)
        if parsed:
            normal.append(parsed)
    return CashierPayWaysParsed(normal=normal)


def parse_cashier_pay_ways_response(
    resp: dict,
) -> tuple[bool, str, Optional[CashierPayWaysParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_cashier_pay_ways_data(data) if success and data else None
    return success, message, parsed


def choose_pay_way(parsed: Optional[CashierPayWaysParsed], pay_way_name: str) -> Optional[CashierPayWayItem]:
    if parsed is None:
        return None
    for item in parsed.normal:
        if item.name == pay_way_name:
            return item
    return None


@dataclass
class CashierPayResultParsed:
    transaction_id: str
    is_paid: bool
    pay_url: str
    pay_qr_code: str
    pay_web_form: str
    wxpay_jsapi_data_str: str


def parse_cashier_pay_result_data(data: dict) -> Optional[CashierPayResultParsed]:
    if not isinstance(data, dict):
        return None
    return CashierPayResultParsed(
        transaction_id=str(data.get("transactionId") or ""),
        is_paid=bool(data.get("isPaid", False)),
        pay_url=str(data.get("payUrl") or ""),
        pay_qr_code=str(data.get("payQrCode") or ""),
        pay_web_form=str(data.get("payWebForm") or ""),
        wxpay_jsapi_data_str=str(data.get("wxpayJsapiDataStr") or ""),
    )


def parse_cashier_pay_response(
    resp: dict,
) -> tuple[bool, str, Optional[CashierPayResultParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_cashier_pay_result_data(data) if success and data else None
    return success, message, parsed


def extract_weixin_scheme(html: str) -> str:
    match = WAP_DEEPLINK_RE.search(html or "")
    return match.group(1) if match else ""
