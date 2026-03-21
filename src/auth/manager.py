from __future__ import annotations

import logging
import time
import uuid

from src.api.auth_api import AuthApi
from src.api.client import ApiClient
from src.auth.cgyy_auth_service import CgyyAuthService
from src.auth.exceptions import AuthUnavailableError
from src.auth.models import AuthBootstrapResult, ServiceAuthState
from src.auth.services import AuthProbeService, SsoBootstrapService
from src.config.env_store import EnvStore
from src.config.settings import ApiSettings, AuthSettings, SsoSettings
from src.sso.models import Credentials
from src.utils.sign_utils import SignBuilder

logger = logging.getLogger(__name__)


class AuthManager:
    def __init__(
        self,
        api_settings: ApiSettings,
        auth_settings: AuthSettings,
        sso_settings: SsoSettings,
        env_store: EnvStore | None = None,
    ) -> None:
        self.api_settings = api_settings
        self.auth_settings = auth_settings
        self.sso_settings = sso_settings
        self.env_store = env_store or EnvStore()
        self.probe_service = AuthProbeService(api_settings)
        self.sso_bootstrap_service = SsoBootstrapService(api_settings, sso_settings)

    def _fingerprint(self, token: str) -> str:
        if not token:
            return "-"
        if len(token) <= 12:
            return f"{token[:4]}...{len(token)}"
        return f"{token[:8]}...{len(token)}"

    def _apply_state(self, state: ServiceAuthState) -> None:
        self.auth_settings.cookie = state.cookie
        if state.cg_authorization:
            self.auth_settings.cg_authorization = state.cg_authorization

    def _exchange_cg_authorization(self, state: ServiceAuthState) -> str:
        auth_context = state.to_auth_context()
        sso_token = auth_context.get_cookie("sso_buaa_token")
        if not sso_token:
            raise AuthUnavailableError("SSO 登录完成，但未在 cookie 中找到 sso_buaa_token")
        auth = AuthSettings(cookie=state.cookie, cg_authorization="")
        client = ApiClient(
            api_settings=self.api_settings,
            auth_settings=auth,
            sign_builder=SignBuilder(prefix=self.api_settings.prefix),
            retry_count=self.api_settings.retry_count,
            retry_interval_sec=self.api_settings.retry_interval_sec,
        )
        auth_service = CgyyAuthService(AuthApi(client=client))
        result = auth_service.exchange_cg_authorization(sso_token)
        logger.info(
            "业务鉴权完成 role_id=%s initial_token=%s final_token=%s",
            result.role_id,
            self._fingerprint(result.login_parsed.access_token if result.login_parsed else ""),
            self._fingerprint(result.cg_authorization),
        )
        return result.cg_authorization

    def _persist_auth(self, state: ServiceAuthState) -> None:
        if not self.sso_settings.persist_to_env:
            logger.info("已跳过鉴权持久化（CGYY_AUTH_PERSIST_TO_ENV=0）")
            return
        self.env_store.set_values(
            {
                "CGYY_COOKIE": state.cookie,
                "CGYY_CG_AUTH": state.cg_authorization,
            },
            persist=True,
            update_environ=True,
        )

    def ensure_cgyy_auth(self) -> AuthBootstrapResult:
        flow_id = uuid.uuid4().hex[:8]
        current_state = ServiceAuthState(
            service_name="cgyy",
            cookie=self.auth_settings.cookie,
            cg_authorization=self.auth_settings.cg_authorization,
            obtained_at=time.time(),
            source="env",
        )
        logger.info("认证流程开始 flow_id=%s", flow_id)
        if self.probe_service.probe(current_state.to_auth_context()):
            logger.info("复用当前认证信息 flow_id=%s source=env", flow_id)
            return AuthBootstrapResult(
                reused=True,
                refreshed=False,
                state=current_state,
            )

        if not self.sso_settings.enabled:
            raise AuthUnavailableError("当前认证失效，且未启用 SSO 自动登录")
        if not self.sso_settings.login_base_url or not self.sso_settings.service_url:
            raise AuthUnavailableError("SSO 已启用，但未配置登录地址或服务地址")
        if not self.sso_settings.username or not self.sso_settings.password:
            raise AuthUnavailableError("SSO 已启用，但未配置账号密码")

        logger.info("开始执行 SSO 自动登录 flow_id=%s", flow_id)
        state = self.sso_bootstrap_service.login(
            Credentials(
                username=self.sso_settings.username,
                password=self.sso_settings.password,
            ),
            current_state.to_auth_context(),
        )
        if not state.cookie:
            raise AuthUnavailableError("SSO 登录完成，但未获取到服务 cookie")
        state.cg_authorization = self._exchange_cg_authorization(state)
        if not state.cg_authorization:
            raise AuthUnavailableError("SSO 登录完成，但未换取到 cgAuthorization")
        self._apply_state(state)
        state.obtained_at = time.time()
        self._persist_auth(state)
        logger.info(
            "认证流程完成 flow_id=%s source=sso cookie_keys=%s cg_auth=%s",
            flow_id,
            ",".join(sorted(state.to_auth_context().cookies.keys())),
            self._fingerprint(state.cg_authorization),
        )
        return AuthBootstrapResult(reused=False, refreshed=True, state=state)

    def get_cgyy_auth_status(self) -> AuthBootstrapResult:
        current_state = ServiceAuthState(
            service_name="cgyy",
            cookie=self.auth_settings.cookie,
            cg_authorization=self.auth_settings.cg_authorization,
            obtained_at=time.time(),
            source="env",
        )
        ok = self.probe_service.probe(current_state.to_auth_context())
        if ok:
            return AuthBootstrapResult(reused=True, refreshed=False, state=current_state)
        return AuthBootstrapResult(reused=False, refreshed=False, state=current_state)

    def clear_cgyy_auth(self) -> None:
        self.auth_settings.cookie = ""
        self.auth_settings.cg_authorization = ""
        self.env_store.set_values(
            {
                "CGYY_COOKIE": "",
                "CGYY_CG_AUTH": "",
            },
            persist=True,
            update_environ=True,
        )
        self.env_store.clear_environ_keys(["CGYY_COOKIE", "CGYY_CG_AUTH"])
