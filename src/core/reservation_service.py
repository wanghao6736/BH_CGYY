from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.api.reservation_api import ReservationApi
from src.config.settings import ApiSettings, UserSettings
from src.parsers.common import parse_success_message
from src.parsers.day_info import DayInfoParsed, parse_info_response
from src.parsers.order import (OrderDetailParsed, SubmitParsed,
                               parse_order_detail_response,
                               parse_submit_response)
from src.utils.crypto_utils import AesCbcEncryptor


@dataclass
class ReservationResult:
    success: bool
    message: str
    raw: Dict[str, Any]
    submit_parsed: Optional[SubmitParsed] = None


class ReservationService:
    def __init__(
        self,
        api: ReservationApi,
        api_settings: ApiSettings,
        user_settings: UserSettings,
        order_pin_encryptor: AesCbcEncryptor,
    ) -> None:
        self.api = api
        self.api_settings = api_settings
        self.user_settings = user_settings
        self.order_pin_encryptor = order_pin_encryptor

    def get_info_parsed(
        self, search_date: Optional[str] = None, has_reserve_info: bool = False
    ) -> tuple[bool, str, Optional[DayInfoParsed]]:
        """Fetch info and parse via parsers; no parsing logic here. Returns (success, message, parsed)."""
        raw = self.api.get_info(search_date=search_date, has_reserve_info=has_reserve_info)
        return parse_info_response(raw)

    def get_order_detail_parsed(
        self, venue_trade_no: str
    ) -> tuple[bool, str, Optional[OrderDetailParsed]]:
        """Fetch order detail and parse. Returns (success, message, OrderDetailParsed | None)."""
        raw = self.api.get_order_info(venue_trade_no)
        return parse_order_detail_response(raw)

    def cancel_order_parsed(self, venue_trade_no: str) -> tuple[bool, str]:
        """Fetch cancel order and parse. Returns (success, message)."""
        raw = self.api.cancel_order(venue_trade_no)
        return parse_success_message(raw)

    def _build_order_pin(self, x: Optional[int] = None, y: Optional[int] = None) -> str:
        import random

        if x is None:
            x = random.randint(
                self.user_settings.order_pin_x_min,
                self.user_settings.order_pin_x_max,
            )
        if y is None:
            y = random.randint(
                self.user_settings.order_pin_y_min,
                self.user_settings.order_pin_y_max,
            )
        data = f"{x},{y}".encode("utf-8")
        return self.order_pin_encryptor.encrypt_hex(data)

    def _build_payload(
        self,
        captcha_token: str,
        captcha_verification: str,
        *,
        reservation_date: Optional[str] = None,
        week_start_date: Optional[str] = None,
        reservation_order_json: Optional[str] = None,
        buddy_ids: Optional[str] = None,
        order_price: Optional[int] = None,
    ) -> Dict[str, Any]:
        order_pin = self._build_order_pin()
        payload: Dict[str, Any] = {
            "captchaToken": captcha_token,
            "captchaVerification": captcha_verification,
            "orderPin": order_pin,
            "orderPrice": order_price if order_price is not None else self.user_settings.order_price,
            "phone": self.user_settings.phone,
            "reservationDate": reservation_date or self.user_settings.reservation_date,
            "reservationOrderJson": reservation_order_json or self.user_settings.reservation_order_json,
            "reservationType": self.user_settings.reservation_type,
            "venueSiteId": self.api_settings.venue_site_id,
            "weekStartDate": week_start_date or self.user_settings.week_start_date,
        }

        # buddyIds/buddyUids：当场地不需要同伴时应完全不传（而不是传空串）。
        # - buddy_ids=None：沿用配置默认
        # - buddy_ids=""：显式不传同伴参数
        final_buddy_ids = buddy_ids if buddy_ids is not None else self.user_settings.buddy_ids
        if final_buddy_ids:
            payload["buddyIds"] = final_buddy_ids
            payload["buddyUids"] = ""
        return payload

    def submit_reservation(
        self,
        captcha_token: str,
        captcha_verification: str,
        *,
        reservation_date: Optional[str] = None,
        week_start_date: Optional[str] = None,
        reservation_order_json: Optional[str] = None,
        buddy_ids: Optional[str] = None,
        order_price: Optional[int] = None,
    ) -> ReservationResult:
        payload = self._build_payload(
            captcha_token,
            captcha_verification,
            reservation_date=reservation_date,
            week_start_date=week_start_date,
            reservation_order_json=reservation_order_json,
            buddy_ids=buddy_ids,
            order_price=order_price,
        )
        resp = self.api.submit_order(payload)
        success, message, submit_parsed = parse_submit_response(resp)
        return ReservationResult(
            success=success, message=message, raw=resp, submit_parsed=submit_parsed
        )
