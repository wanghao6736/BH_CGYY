from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from urllib.parse import quote

from src.api.cashier_client import CashierClient
from src.api.endpoints import CashierEndpoints
from src.http.header_profiles import CASHIER_MOBILE_USER_AGENT
from src.utils.time_utils import current_timestamp_ms


@dataclass
class CashierApi:
    client: CashierClient

    @staticmethod
    def build_wap_request_url(pay_url: str, cashier_origin: str, cashier_id: str) -> str:
        redirect_url = f"{cashier_origin}/cashier?id={cashier_id}&for=wxpay_wap"
        if "redirect_url=" in pay_url:
            return pay_url
        separator = "&" if "?" in pay_url else "?"
        return f"{pay_url}{separator}redirect_url={quote(redirect_url, safe='')}"

    def get_transaction(self, cashier_id: str, referer: str) -> Dict[str, Any]:
        ts = current_timestamp_ms()
        rel_path = f"{CashierEndpoints.TRANSACTION}?_t=={ts}&id={cashier_id}"
        return self.client.get_json(rel_path, referer=referer)

    def get_pay_ways(self, goods_id: str, pay_scene: str, referer: str) -> Dict[str, Any]:
        ts = current_timestamp_ms()
        rel_path = (
            f"{CashierEndpoints.PAY_WAYS}?_t=={ts}"
            f"&payScene={pay_scene}&goodsId={goods_id}"
        )
        return self.client.get_json(rel_path, referer=referer)

    def pay(
        self,
        cashier_id: str,
        pay_way_id: str,
        referer: str,
        phone_number: str = "",
        ec_code: str = "",
    ) -> Dict[str, Any]:
        ts = current_timestamp_ms()
        rel_path = (
            f"{CashierEndpoints.TRANSACTION_PAY}?_t=={ts}"
            f"&id={cashier_id}&payWayId={pay_way_id}"
            f"&phoneNumber={phone_number}&ecCode={ec_code}"
        )
        return self.client.get_json(rel_path, referer=referer)

    def fetch_wap_page(
        self,
        pay_url: str,
        *,
        cashier_origin: str,
        cashier_id: str,
        referer: str,
    ) -> str:
        request_url = self.build_wap_request_url(pay_url, cashier_origin, cashier_id)
        return self.client.get_text(
            request_url,
            referer=referer,
            user_agent=CASHIER_MOBILE_USER_AGENT,
        )
