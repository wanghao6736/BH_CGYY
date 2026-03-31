from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urljoin, urlsplit

from src.auth.exceptions import CashierBootstrapError
from src.auth.models import AuthContext, ServiceAuthState
from src.config.settings import BUAA_CGYY_REFERER, SsoSettings
from src.http.header_profiles import (DESKTOP_BROWSER_USER_AGENT,
                                      build_page_headers)
from src.sso.adapters.cashier_adapter import CashierAdapter
from src.sso.api.page_client import PageClient
from src.sso.exceptions import SsoError
from src.sso.models import Credentials
from src.sso.providers.cas_provider import CasProvider
from src.sso.service import SsoLoginService

logger = logging.getLogger(__name__)


@dataclass
class CashierBootstrapService:
    sso_settings: SsoSettings = field(default_factory=SsoSettings)
    timeout_sec: float = 15.0
    retry_count: int = 3
    retry_interval_sec: float = 2.0
    user_agent: str = DESKTOP_BROWSER_USER_AGENT
    max_redirects: int = 10

    def _build_page_client(self, cookie_header: str = "") -> PageClient:
        page_client = PageClient(
            timeout_sec=self.timeout_sec,
            retry_count=self.retry_count,
            retry_interval_sec=self.retry_interval_sec,
        )
        page_client._headers["User-Agent"] = self.user_agent
        if cookie_header:
            auth_context = AuthContext.from_cookie_header(cookie_header)
            for name, value in auth_context.cookies.items():
                page_client._session.cookies.set(name, value)
        return page_client

    def _request_redirect(self, page_client: PageClient, url: str, referer: str):
        response = page_client.get_page(
            url,
            headers=build_page_headers(referer=referer, user_agent=self.user_agent),
        )
        if response.status_code >= 400:
            raise CashierBootstrapError(f"cashier bootstrap 返回异常状态码: {response.status_code}")
        return response

    def _extract_service_url(self, sso_login_url: str) -> str:
        query = parse_qs(urlsplit(sso_login_url).query)
        service_url = query.get("service", [""])[0]
        if not service_url:
            raise CashierBootstrapError("cashier SSO 跳转地址缺少 service 参数")
        return service_url

    def _login_base_url(self, sso_login_url: str) -> str:
        if self.sso_settings.login_base_url:
            return self.sso_settings.login_base_url
        parts = urlsplit(sso_login_url)
        return f"{parts.scheme}://{parts.netloc}{parts.path}"

    def _complete_sso_login(
        self,
        page_client: PageClient,
        *,
        sso_login_url: str,
        cashier_url: str,
    ) -> ServiceAuthState:
        provider = CasProvider(login_base_url=self._login_base_url(sso_login_url))
        adapter = CashierAdapter(
            service_url=self._extract_service_url(sso_login_url),
            cashier_url=cashier_url,
        )
        service = SsoLoginService(
            provider=provider,
            page_client=page_client,
            max_redirects=self.sso_settings.max_redirects or self.max_redirects,
        )
        credentials = Credentials(
            username=self.sso_settings.username,
            password=self.sso_settings.password,
        )
        try:
            result = service.login(adapter, credentials)
        except SsoError as exc:
            raise CashierBootstrapError(f"cashier 统一认证失败：{exc}") from exc
        logger.info(
            "cashier SSO 自动回跳完成 final_url=%s redirect_count=%d",
            result.final_url,
            len(result.redirect_chain),
        )
        return adapter.collect_auth_state(service.page_client)

    def bootstrap_from_school_pay_url(
        self,
        cashier_url: str,
        *,
        cookie_header: str = "",
    ) -> ServiceAuthState:
        page_client = self._build_page_client(cookie_header)

        entry = self._request_redirect(page_client, cashier_url, BUAA_CGYY_REFERER)
        if not entry.location:
            raise CashierBootstrapError("cashier 入口未返回跳转地址")
        pass_login_url = urljoin(cashier_url, entry.location)

        pass_login = self._request_redirect(page_client, pass_login_url, cashier_url)
        if not pass_login.location:
            raise CashierBootstrapError("pass.cc-pay 登录入口未返回跳转地址")
        sso_login_url = urljoin(pass_login_url, pass_login.location)
        logger.info("cashier bootstrap 获取 SSO 跳转地址: %s", sso_login_url)
        auth_state = self._complete_sso_login(
            page_client,
            sso_login_url=sso_login_url,
            cashier_url=cashier_url,
        )
        if not auth_state.cookie:
            raise CashierBootstrapError("cashier bootstrap 未获取到可用 cookie")
        if "user_id=" not in auth_state.cookie:
            raise CashierBootstrapError("cashier bootstrap 未完成登录，缺少 user_id cookie")
        return auth_state
