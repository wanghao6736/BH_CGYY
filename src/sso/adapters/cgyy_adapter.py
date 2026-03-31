from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from src.auth.models import ServiceAuthState
from src.sso.api.page_client import PageClient
from src.sso.models import PageResponse

logger = logging.getLogger(__name__)


@dataclass
class CgyyAdapter:
    service_url: str
    portal_path_keyword: str = "/venue/"
    auth_header_name: str = "cgAuthorization"

    @property
    def service_name(self) -> str:
        return "cgyy"

    def is_service_response(self, resp: PageResponse) -> bool:
        url = resp.url or ""
        if self.portal_path_keyword and self.portal_path_keyword in url:
            return True
        if "统一身份认证" in (resp.text or ""):
            return False
        return "公共空间资源服务门户" in (resp.text or "") or "智慧场馆" in (resp.text or "")

    def build_portal_url(self) -> str:
        parsed = urlparse(self.service_url)
        return f"{parsed.scheme}://{parsed.netloc}/venue/login"

    def initialize_service_session(
        self,
        page_client: PageClient,
        current_response: PageResponse | None = None,
    ) -> PageResponse:
        if current_response is not None and self.is_service_response(current_response):
            logger.info("当前已位于服务页面，无需额外初始化 service=%s url=%s", self.service_name, current_response.url)
            return current_response
        portal_url = self.build_portal_url()
        logger.info("初始化服务会话 service=%s url=%s", self.service_name, portal_url)
        return page_client.get_page(portal_url)

    def collect_auth_state(self, page_client: PageClient) -> ServiceAuthState:
        cookies = page_client.cookies_dict()
        cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
        cg_auth = ""
        if self.auth_header_name in page_client._headers:
            cg_auth = str(page_client._headers[self.auth_header_name])
        return ServiceAuthState(
            service_name=self.service_name,
            cookie=cookie,
            cg_authorization=cg_auth,
            source="sso",
        )
