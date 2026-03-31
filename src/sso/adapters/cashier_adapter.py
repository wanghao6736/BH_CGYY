from __future__ import annotations

from dataclasses import dataclass

from src.auth.models import ServiceAuthState
from src.sso.api.page_client import PageClient
from src.sso.models import PageResponse


@dataclass
class CashierAdapter:
    service_url: str
    cashier_url: str
    cashier_host: str = "cashier.cc-pay.cn"

    @property
    def service_name(self) -> str:
        return "cashier"

    def is_service_response(self, resp: PageResponse) -> bool:
        url = resp.url or ""
        return self.cashier_host in url and "/cashier" in url

    def initialize_service_session(
        self,
        page_client: PageClient,
        current_response: PageResponse | None = None,
    ) -> PageResponse:
        if current_response is not None and self.is_service_response(current_response):
            return current_response
        return page_client.get_page(self.cashier_url)

    def collect_auth_state(self, page_client: PageClient) -> ServiceAuthState:
        cookies = page_client.cookies_dict()
        wanted = ["connect.sid", "user_id", "avatar_dir"]
        cookie = "; ".join(f"{name}={cookies[name]}" for name in wanted if cookies.get(name))
        return ServiceAuthState(
            service_name=self.service_name,
            cookie=cookie,
            source="cashier",
        )
