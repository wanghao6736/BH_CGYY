from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.api.client import ApiClient
from src.config.settings import ApiSettings, UserSettings
from src.utils.sign_utils import params_to_sign_parts

REL_info = "/api/reservation/day/info"
REL_SUBMIT = "/api/reservation/order/submit"
REL_DETAIL = "/api/venue/finances/order/detail"
REL_CANCEL = "/api/venue/finances/order/cancel"


@dataclass
class ReservationApi:
    client: ApiClient
    api_settings: ApiSettings
    user_settings: UserSettings

    def get_info(self, search_date: str | None = None, hasReserveInfo: bool = False) -> Dict[str, Any]:
        if search_date is None:
            search_date = self.api_settings.default_search_date
        venue_site_id = self.api_settings.venue_site_id
        from src.utils.time_utils import current_timestamp_ms

        ts = current_timestamp_ms()
        params = {
            "venueSiteId": venue_site_id,
            "searchDate": search_date,
            "nocache": ts,
        }
        if hasReserveInfo:
            params["hasReserveInfo"] = 1
        sign_parts = params_to_sign_parts(params)
        return self.client.get(REL_info, params=params, sign_parts=sign_parts)

    def get_order_info(self, venueTradeNo: str) -> Dict[str, Any]:
        from src.utils.time_utils import current_timestamp_ms

        ts = current_timestamp_ms()
        params = {
            "venueTradeNo": venueTradeNo,
            "nocache": ts,
        }
        sign_parts = params_to_sign_parts(params)
        return self.client.get(REL_DETAIL, params=params, sign_parts=sign_parts)

    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sign_keys = [
            "buddyIds", "captchaToken", "captchaVerification", "orderPin",
            "orderPrice", "phone", "reservationDate", "reservationOrderJson",
            "reservationType", "venueSiteId", "weekStartDate",
        ]
        # buddyIds 在部分场地（buddyNumMin==0）可能不需要传，此时不参与签名
        sign_params = {k: payload[k] for k in sign_keys if k in payload}
        sign_parts = params_to_sign_parts(sign_params)
        return self.client.post(REL_SUBMIT, data=payload, sign_parts=sign_parts)

    def cancel_order(self, venueTradeNo: str) -> Dict[str, Any]:
        params = {
            "venueTradeNo": venueTradeNo,
            # "remark": "",
        }
        sign_parts = params_to_sign_parts(params)
        return self.client.post(REL_CANCEL, data=params, sign_parts=sign_parts)
