from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from src.http.base_client import BaseHttpClient
from src.sso.models import PageResponse

logger = logging.getLogger(__name__)


@dataclass
class PageClient(BaseHttpClient):
    timeout_sec: float = 10.0

    def __post_init__(self) -> None:
        self._session.headers.update(
            {
                "user-agent": "Mozilla/5.0",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def _request(self, method: str, url: str, **kwargs: object) -> PageResponse:
        resp = self._request_with_retry(
            method,
            url,
            log_prefix="页面",
            timeout=self.timeout_sec,
            allow_redirects=False,
            **kwargs,
        )
        return PageResponse(
            url=str(resp.url),
            status_code=resp.status_code,
            headers=dict(resp.headers),
            text=resp.text,
        )

    def get_page(self, url: str, params: Optional[Dict[str, str]] = None) -> PageResponse:
        return self._request("get", url, params=params)

    def post_form(
        self,
        url: str,
        data: Dict[str, str],
        headers: Optional[Dict[str, str]] = None,
    ) -> PageResponse:
        req_headers = {"content-type": "application/x-www-form-urlencoded"}
        if headers:
            req_headers.update(headers)
        return self._request("post", url, data=data, headers=req_headers)

    def cookies_dict(self) -> Dict[str, str]:
        return self._session.cookies.get_dict()
