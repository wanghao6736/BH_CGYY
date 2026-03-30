"""Parse info API response (data section). Pure functions on dict, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.parsers.common import get_by_path

# Keys in each space object that are not timeId slots
_SPACE_FIXED_KEYS = frozenset({"id", "venueSiteId", "spaceName", "enSpaceName", "venueSpaceGroupId"})


@dataclass
class TimeSlot:
    id: int
    begin_time: str
    end_time: str


@dataclass
class SlotState:
    """reservationStatus: 1=可预定, 2=系统锁定, 3=待付款, 4=已预定。is_available 由 reservation_status==1 判定。"""

    reservation_status: int
    is_available: bool
    order_fee: Optional[float] = 0
    trade_no: Optional[str] = None
    use_num: Optional[int] = None
    wait_num: Optional[int] = None
    already_num: Optional[int] = None


@dataclass
class SpaceSchedule:
    space_id: int
    space_name: str
    venue_site_id: int
    slots: Dict[str, SlotState]  # timeId (str) -> state


@dataclass
class Buddy:
    id: int
    name: str
    user_id: int


@dataclass
class OrderParamView:
    phone: str
    buddy_list: List[Buddy]


@dataclass
class SiteParam:
    site_name: str
    venue_name: str
    campus_name: str
    venue_site_id: int
    buddy_num_min: int = 0
    buddy_num_max: int = 0


@dataclass
class DayInfoParsed:
    reservation_date_list: List[str]
    time_slots: List[TimeSlot]
    space_schedules_by_date: Dict[str, List[SpaceSchedule]]  # date -> list of SpaceSchedule
    order_param_view: Optional[OrderParamView]
    site_param: Optional[SiteParam]


def _slot_state_from_raw(raw: Dict[str, Any]) -> SlotState:
    status = raw.get("reservationStatus")
    if status is None:
        status = 4  # 缺省视为已占用
    return SlotState(
        reservation_status=int(status),
        is_available=(int(status) == 1),
        order_fee=raw.get("orderFee") or 0,
        trade_no=raw.get("tradeNo"),
        use_num=raw.get("useNum"),
        wait_num=raw.get("waitNum"),
        already_num=raw.get("alreadyNum"),
    )


def parse_space_time_info(data: Dict[str, Any]) -> List[TimeSlot]:
    """Parse data.spaceTimeInfo into list of TimeSlot (sorted by begin_time)."""
    raw_list = get_by_path(data, "spaceTimeInfo") or []
    out = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        tid = item.get("id")
        if tid is None:
            continue
        out.append(
            TimeSlot(
                id=int(tid),
                begin_time=str(item.get("beginTime", "")),
                end_time=str(item.get("endTime", "")),
            )
        )
    out.sort(key=lambda t: t.begin_time)
    return out


def parse_reservation_date_space_info(
    data: Dict[str, Any], date: Optional[str] = None
) -> Dict[str, List[SpaceSchedule]]:
    """
    Parse data.reservationDateSpaceInfo.
    Returns dict: date -> list of SpaceSchedule.
    If date is given, only that date is parsed; else all dates in the map.
    """
    by_date = get_by_path(data, "reservationDateSpaceInfo") or {}
    if not isinstance(by_date, dict):
        return {}
    dates = [date] if date else list(by_date.keys())
    result: Dict[str, List[SpaceSchedule]] = {}
    for d in dates:
        space_list = by_date.get(d)
        if not isinstance(space_list, list):
            result[d] = []
            continue
        schedules = []
        for item in space_list:
            if not isinstance(item, dict):
                continue
            space_id = item.get("id")
            if space_id is None:
                continue
            space_name = str(item.get("spaceName") or "")
            venue_site_id = int(item.get("venueSiteId") or 0)
            slots: Dict[str, SlotState] = {}
            for k, v in item.items():
                if k in _SPACE_FIXED_KEYS:
                    continue
                if isinstance(v, dict):
                    slots[str(k)] = _slot_state_from_raw(v)
            schedules.append(
                SpaceSchedule(
                    space_id=int(space_id),
                    space_name=space_name,
                    venue_site_id=venue_site_id,
                    slots=slots,
                )
            )
        result[d] = schedules
    return result


def parse_order_param_view(data: Dict[str, Any]) -> Optional[OrderParamView]:
    """Parse data.orderParamView -> phone, buddyList (id, name, userId)."""
    view = get_by_path(data, "orderParamView")
    if not isinstance(view, dict):
        return None
    phone = str(view.get("phone") or "")
    buddy_list: List[Buddy] = []
    for b in view.get("buddyList") or []:
        if not isinstance(b, dict):
            continue
        bid, name, uid = b.get("id"), b.get("name"), b.get("userId")
        if bid is None or uid is None:
            continue
        buddy_list.append(Buddy(id=int(bid), name=str(name or ""), user_id=int(uid)))
    return OrderParamView(phone=phone, buddy_list=buddy_list)


def parse_site_param(data: Dict[str, Any]) -> Optional[SiteParam]:
    """Parse data.siteParam -> siteName, venueName, campusName, venueSiteId."""
    sp = get_by_path(data, "siteParam")
    if not isinstance(sp, dict):
        return None
    return SiteParam(
        site_name=str(sp.get("siteName") or ""),
        venue_name=str(sp.get("venueName") or ""),
        campus_name=str(sp.get("campusName") or ""),
        venue_site_id=int(sp.get("venueSiteId") or 0),
        buddy_num_min=int(sp.get("buddyNumMin") or 0),
        buddy_num_max=int(sp.get("buddyNumMax") or 0),
    )


def parse_info_data(data: Dict[str, Any]) -> DayInfoParsed:
    """
    Parse full info data section. Use with data = resp["data"] or load from JSON file.
    """
    reservation_date_list = get_by_path(data, "reservationDateList") or []
    if not isinstance(reservation_date_list, list):
        reservation_date_list = []
    time_slots = parse_space_time_info(data)
    space_schedules_by_date = parse_reservation_date_space_info(data)
    return DayInfoParsed(
        reservation_date_list=reservation_date_list,
        time_slots=time_slots,
        space_schedules_by_date=space_schedules_by_date,
        order_param_view=parse_order_param_view(data),
        site_param=parse_site_param(data),
    )


def parse_info_response(resp: Dict[str, Any]) -> tuple[bool, str, Optional[DayInfoParsed]]:
    """
    Parse full info API response. Returns (success, message, parsed_data).
    parsed_data is None when success is False.
    """
    from src.parsers.common import parse_success_message

    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_info_data(data) if success and data else None
    return success, message, parsed
