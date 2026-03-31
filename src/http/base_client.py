from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class BaseHttpClient:
    session: Optional[requests.Session] = None
    retry_count: int = 3
    retry_interval_sec: float = 2.0

    @property
    def _session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
        return self.session

    @property
    def _headers(self) -> Dict[str, str]:
        return self._session.headers

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        log_prefix: str,
        retry_on_4xx: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        attempts = max(self.retry_count, 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = self._session.request(method, url, **kwargs)
                resp.raise_for_status()
                logger.info("%s %s %s -> %s", log_prefix, method.upper(), url, resp.status_code)
                return resp
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if not retry_on_4xx and 400 <= status < 500:
                    logger.warning("%s HTTP %d (不可重试): %s %s", log_prefix, status, method.upper(), url)
                    raise
                last_exc = e
            except requests.RequestException as e:
                last_exc = e
            if attempt < attempts - 1:
                logger.info(
                    "%s 请求失败，%0.1fs 后重试 (%d/%d): %s",
                    log_prefix,
                    self.retry_interval_sec,
                    attempt + 1,
                    attempts,
                    last_exc,
                )
                time.sleep(self.retry_interval_sec)
        raise last_exc or RuntimeError(f"{log_prefix}请求失败: {method.upper()} {url}")
