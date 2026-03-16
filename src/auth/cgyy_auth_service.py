from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.api.auth_api import AuthApi
from src.parsers.auth import AuthTokenParsed, parse_auth_token_response

logger = logging.getLogger(__name__)


@dataclass
class CgyyAuthExchangeResult:
    cg_authorization: str
    role_id: int
    login_parsed: Optional[AuthTokenParsed] = None
    role_login_parsed: Optional[AuthTokenParsed] = None


class CgyyAuthService:
    def __init__(self, api: AuthApi, default_role_id: int = 3) -> None:
        self.api = api
        self.default_role_id = default_role_id

    def _choose_role_id(self, parsed: Optional[AuthTokenParsed]) -> int:
        if parsed and parsed.roles:
            for role in parsed.roles:
                if role.id == self.default_role_id:
                    return role.id
            return parsed.roles[0].id
        return self.default_role_id

    def exchange_cg_authorization(self, sso_token: str) -> CgyyAuthExchangeResult:
        logger.info("调用业务登录接口，使用 sso-token 换取初始业务 token")
        login_raw = self.api.login_with_sso_token(sso_token)
        ok, msg, login_parsed = parse_auth_token_response(login_raw)
        if not ok or not login_parsed:
            raise RuntimeError(f"业务登录失败：{msg}")

        role_id = self._choose_role_id(login_parsed)
        logger.info("调用角色登录接口 role_id=%s", role_id)
        role_raw = self.api.role_login(role_id, login_parsed.access_token)
        ok, msg, role_parsed = parse_auth_token_response(role_raw)
        if not ok or not role_parsed:
            raise RuntimeError(f"角色登录失败：{msg}")

        return CgyyAuthExchangeResult(
            cg_authorization=role_parsed.access_token,
            role_id=role_id,
            login_parsed=login_parsed,
            role_login_parsed=role_parsed,
        )
