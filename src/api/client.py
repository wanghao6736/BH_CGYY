from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import requests

from src.config.settings import ApiSettings, AuthSettings
from src.utils.sign_utils import SignBuilder
from src.utils.time_utils import current_timestamp_ms

logger = logging.getLogger(__name__)


@dataclass
class ApiClient:
    api_settings: ApiSettings
    auth_settings: AuthSettings
    sign_builder: SignBuilder
    session: Optional[requests.Session] = None
    retry_count: int = 3
    retry_interval_sec: float = 2.0

    @property
    def _session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
        return self.session

    def _base_headers(self, timestamp: int) -> Dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": self.auth_settings.cookie,
            "cgAuthorization": self.auth_settings.cg_authorization,
            "app-key": self.api_settings.app_key,
            "timestamp": str(timestamp),
        }

    def _build_sign(
        self, rel_path: str, parts: Iterable[str], timestamp: int
    ) -> str:
        extended_parts = list(parts) + [f"{timestamp} {self.api_settings.prefix}"]
        return self.sign_builder.build(rel_path, extended_parts)

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        attempts = max(self.retry_count, 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = self._session.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if 400 <= status < 500:
                    logger.warning("HTTP %d (不可重试): %s %s", status, method.upper(), url)
                    raise
                last_exc = e
            except requests.RequestException as e:
                last_exc = e
            if attempt < attempts - 1:
                logger.info("请求失败，%0.1fs 后重试 (%d/%d)", self.retry_interval_sec, attempt + 1, attempts)
                time.sleep(self.retry_interval_sec)
        raise last_exc or RuntimeError(f"请求失败: {method.upper()} {url}")

    def get(
        self,
        rel_path: str,
        params: Dict[str, Any],
        sign_parts: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        timestamp = current_timestamp_ms()
        headers = self._base_headers(timestamp)
        if sign_parts is not None:
            headers["sign"] = self._build_sign(rel_path, sign_parts, timestamp)
        url = f"{self.api_settings.base_url}{rel_path}"
        resp = self._request_with_retry("get", url, headers=headers, params=params)
        return resp.json()

    def post(
        self,
        rel_path: str,
        data: Dict[str, Any],
        sign_parts: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        timestamp = current_timestamp_ms()
        headers = self._base_headers(timestamp)
        if sign_parts is not None:
            headers["sign"] = self._build_sign(rel_path, sign_parts, timestamp)
        url = f"{self.api_settings.base_url}{rel_path}"
        resp = self._request_with_retry("post", url, headers=headers, data=data)
        return resp.json()
