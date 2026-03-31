from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.auth.models import AuthContext
from src.http.base_client import BaseHttpClient
from src.http.header_profiles import (DESKTOP_BROWSER_USER_AGENT,
                                      HTML_ACCEPT, JSON_ACCEPT,
                                      build_cashier_headers)


@dataclass(kw_only=True)
class CashierClient(BaseHttpClient):
    base_url: str
    cookie: str = ""
    user_agent: str = DESKTOP_BROWSER_USER_AGENT
    timeout_sec: float = 15.0

    def __post_init__(self) -> None:
        self._headers.update(build_cashier_headers(referer="", accept=JSON_ACCEPT, user_agent=self.user_agent))
        self._headers.pop("Referer", None)
        if self.cookie:
            self.apply_cookie_header(self.cookie)

    def apply_cookie_header(self, cookie_header: str) -> None:
        auth_context = AuthContext.from_cookie_header(cookie_header)
        for name, value in auth_context.cookies.items():
            self._session.cookies.set(name, value)

    def _resolve_url(self, rel_path_or_url: str) -> str:
        if rel_path_or_url.startswith("http://") or rel_path_or_url.startswith("https://"):
            return rel_path_or_url
        return f"{self.base_url}{rel_path_or_url}"

    def _request_headers(
        self,
        *,
        referer: str,
        accept: str,
        version: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        return build_cashier_headers(
            referer=referer,
            accept=accept,
            user_agent=user_agent or self.user_agent,
            version=version,
            extra_headers=extra_headers,
        )

    def get_json(
        self,
        rel_path_or_url: str,
        *,
        referer: str,
        version: Optional[str] = "v2",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = self._resolve_url(rel_path_or_url)
        resp = self._request_with_retry(
            "get",
            url,
            log_prefix="Cashier",
            headers=self._request_headers(
                referer=referer,
                accept=JSON_ACCEPT,
                version=version,
                extra_headers=extra_headers,
            ),
            timeout=self.timeout_sec,
        )
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            body = resp.text[:500]
            raise RuntimeError(f"cashier JSON 解析失败: {url} -> {body}") from exc

    def get_text(
        self,
        rel_path_or_url: str,
        *,
        referer: str,
        version: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> str:
        url = self._resolve_url(rel_path_or_url)
        resp = self._request_with_retry(
            "get",
            url,
            log_prefix="Cashier",
            headers=self._request_headers(
                referer=referer,
                accept=HTML_ACCEPT,
                version=version,
                user_agent=user_agent,
                extra_headers=extra_headers,
            ),
            timeout=self.timeout_sec,
        )
        return resp.text
