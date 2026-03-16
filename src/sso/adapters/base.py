from __future__ import annotations

from typing import Protocol

from src.auth.models import ServiceAuthState
from src.sso.api.page_client import PageClient
from src.sso.models import PageResponse


class ServiceAdapter(Protocol):
    @property
    def service_name(self) -> str:
        ...

    @property
    def service_url(self) -> str:
        ...

    def is_service_response(self, resp: PageResponse) -> bool:
        ...

    def initialize_service_session(
        self,
        page_client: PageClient,
        current_response: PageResponse | None = None,
    ) -> PageResponse:
        ...

    def collect_auth_state(self, page_client: PageClient) -> ServiceAuthState:
        ...
