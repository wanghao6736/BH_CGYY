from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from src.config.settings import ApiSettings, AuthSettings
from src.http.base_client import BaseHttpClient
from src.http.header_profiles import build_api_form_headers
from src.utils.sign_utils import SignBuilder
from src.utils.time_utils import current_timestamp_ms

logger = logging.getLogger(__name__)


@dataclass
class ApiClient(BaseHttpClient):
    api_settings: ApiSettings
    auth_settings: AuthSettings
    sign_builder: SignBuilder

    def _base_headers(self, timestamp: int) -> Dict[str, str]:
        headers = build_api_form_headers()
        headers.update(
            {
            "cookie": self.auth_settings.cookie,
            "cgAuthorization": self.auth_settings.cg_authorization,
            "app-key": self.api_settings.app_key,
            "timestamp": str(timestamp),
            }
        )
        return headers

    def _build_sign(
        self, rel_path: str, parts: Iterable[str], timestamp: int
    ) -> str:
        extended_parts = list(parts) + [f"{timestamp} {self.api_settings.prefix}"]
        return self.sign_builder.build(rel_path, extended_parts)

    def get(
        self,
        rel_path: str,
        params: Dict[str, Any],
        sign_parts: Optional[Iterable[str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        timestamp = current_timestamp_ms()
        headers = self._base_headers(timestamp)
        if sign_parts is not None:
            headers["sign"] = self._build_sign(rel_path, sign_parts, timestamp)
        if extra_headers:
            headers.update(extra_headers)
        url = f"{self.api_settings.base_url}{rel_path}"
        resp = self._request_with_retry(
            "get",
            url,
            log_prefix="API",
            headers=headers,
            params=params,
        )
        return resp.json()

    def post(
        self,
        rel_path: str,
        data: Dict[str, Any],
        sign_parts: Optional[Iterable[str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        timestamp = current_timestamp_ms()
        headers = self._base_headers(timestamp)
        if sign_parts is not None:
            headers["sign"] = self._build_sign(rel_path, sign_parts, timestamp)
        if extra_headers:
            headers.update(extra_headers)
        url = f"{self.api_settings.base_url}{rel_path}"
        resp = self._request_with_retry(
            "post",
            url,
            log_prefix="API",
            headers=headers,
            data=data,
        )
        return resp.json()
