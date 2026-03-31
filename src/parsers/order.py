"""Parse submit order & order detail API responses. Pure functions on dict, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.parsers.common import parse_success_message


@dataclass
class SubmitParsed:
    order_id: int
    trade_no: str
    reservation_start_date: str
    reservation_end_date: str


def parse_submit_data(data: dict) -> Optional[SubmitParsed]:
    if not isinstance(data, dict):
        return None
    oid = data.get("id")
    trade_no = data.get("tradeNo")
    start_date = data.get("reservationStartDate")
    end_date = data.get("reservationEndDate")
    if oid is None or not trade_no:
        return None
    return SubmitParsed(
        order_id=int(oid),
        trade_no=str(trade_no),
        reservation_start_date=str(start_date or ""),
        reservation_end_date=str(end_date or ""),
    )


def parse_submit_response(resp: dict) -> tuple[bool, str, Optional[SubmitParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_submit_data(data) if success and data else None
    return success, message, parsed


@dataclass
class OrderPayParsed:
    school_pay_url: str


def parse_order_pay_data(data: dict) -> Optional[OrderPayParsed]:
    if not isinstance(data, dict):
        return None
    school_pay_url = data.get("schoolPayUrl")
    if not school_pay_url:
        return None
    return OrderPayParsed(school_pay_url=str(school_pay_url))


def parse_order_pay_response(resp: dict) -> tuple[bool, str, Optional[OrderPayParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_order_pay_data(data) if success and data else None
    return success, message, parsed


@dataclass
class OrderSpaceItem:
    id: int
    venue_space_id: int
    space_name: str
    start_time: str
    end_time: str
    order_fee: float
    order_uuid: str


@dataclass
class OrderDetailParsed:
    order_id: int
    order_uuid: str
    pay_user_id: int
    order_status: int  # 2 表示已取消
    pay_status: int  # 1 表示已支付
    pay_fee: float
    gmt_create: str
    expire_time: str
    subject: str
    subject_desc: str
    start_date: str
    end_date: str
    space_list: List[OrderSpaceItem]


def _parse_order_space_item(raw: dict) -> Optional[OrderSpaceItem]:
    if not isinstance(raw, dict):
        return None
    oid = raw.get("id")
    if oid is None:
        return None
    return OrderSpaceItem(
        id=int(oid),
        venue_space_id=int(raw.get("venueSpaceId") or 0),
        space_name=str(raw.get("venueSpaceName") or ""),
        start_time=str(raw.get("startTime") or ""),
        end_time=str(raw.get("endTime") or ""),
        order_fee=float(raw.get("orderFee") or 0),
        order_uuid=str(raw.get("orderUuid") or ""),
    )


def parse_order_detail_data(data: dict) -> Optional[OrderDetailParsed]:
    if not isinstance(data, dict):
        return None
    space_list_raw = data.get("spaceList") or []
    space_list = []
    order_uuid = ""
    for item in space_list_raw:
        parsed = _parse_order_space_item(item)
        if parsed:
            space_list.append(parsed)
            if not order_uuid and parsed.order_uuid:
                order_uuid = parsed.order_uuid
    return OrderDetailParsed(
        order_id=int(data.get("orderId") or 0),
        order_uuid=order_uuid,
        pay_user_id=int(data.get("payUserId") or 0),
        order_status=int(data.get("orderStatus") or 0),
        pay_status=int(data.get("payStatus") or 0),
        pay_fee=float(data.get("payFee") or 0),
        gmt_create=str(data.get("gmtCreate") or ""),
        expire_time=str(data.get("expireTime") or ""),
        subject=str(data.get("subject") or ""),
        subject_desc=str(data.get("subjectDesc") or ""),
        start_date=str(data.get("startDate") or ""),
        end_date=str(data.get("endDate") or ""),
        space_list=space_list,
    )


def parse_order_detail_response(resp: dict) -> tuple[bool, str, Optional[OrderDetailParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_order_detail_data(data) if success and data else None
    return success, message, parsed
