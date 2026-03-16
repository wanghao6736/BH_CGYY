from __future__ import annotations

import logging
from dataclasses import dataclass

from src.api.catalog_api import CatalogApi
from src.api.client import ApiClient
from src.auth.models import AuthContext, ServiceAuthState
from src.config.settings import ApiSettings, AuthSettings, SsoSettings
from src.sso.adapters.base import ServiceAdapter
from src.sso.adapters.cgyy_adapter import CgyyAdapter
from src.sso.api.page_client import PageClient
from src.sso.models import Credentials
from src.sso.providers.cas_provider import CasProvider
from src.sso.service import SsoLoginService
from src.utils.sign_utils import SignBuilder

logger = logging.getLogger(__name__)


@dataclass
class AuthProbeService:
    api_settings: ApiSettings

    def probe(self, auth_context: AuthContext) -> bool:
        if not auth_context.cookies:
            return False
        try:
            client = ApiClient(
                api_settings=self.api_settings,
                auth_settings=AuthSettings(
                    cookie=auth_context.cookie_header(),
                    cg_authorization=auth_context.cg_authorization,
                ),
                sign_builder=SignBuilder(prefix=self.api_settings.prefix),
                retry_count=1,
                retry_interval_sec=0.1,
            )
            raw = CatalogApi(client=client).website_init()
            ok = bool(raw.get("code") == 200 or raw.get("repCode") == "0000")
            logger.info("认证探活结果 ok=%s", ok)
            return ok
        except Exception as e:
            logger.warning("认证探活失败: %s", e)
            return False


@dataclass
class SsoBootstrapService:
    api_settings: ApiSettings
    sso_settings: SsoSettings

    def _build_page_client(self, auth_context: AuthContext) -> PageClient:
        page_client = PageClient(
            timeout_sec=self.sso_settings.timeout_sec,
            retry_count=self.api_settings.retry_count,
            retry_interval_sec=self.api_settings.retry_interval_sec,
        )
        for name, value in auth_context.cookies.items():
            page_client._session.cookies.set(name, value)
        if auth_context.cg_authorization:
            page_client._session.headers["cgAuthorization"] = auth_context.cg_authorization
        return page_client

    def _build_service_adapter(self) -> ServiceAdapter:
        return CgyyAdapter(service_url=self.sso_settings.service_url)

    def login(self, credentials: Credentials, auth_context: AuthContext) -> ServiceAuthState:
        provider = CasProvider(login_base_url=self.sso_settings.login_base_url)
        page_client = self._build_page_client(auth_context)
        service = SsoLoginService(
            provider=provider,
            page_client=page_client,
            max_redirects=self.sso_settings.max_redirects,
        )
        adapter = self._build_service_adapter()
        result = service.login(adapter, credentials)
        logger.info(
            "SSO 登录完成 final_url=%s redirect_count=%d",
            result.final_url,
            len(result.redirect_chain),
        )
        return adapter.collect_auth_state(service.page_client)
