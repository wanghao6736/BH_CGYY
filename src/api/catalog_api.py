from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.api.client import ApiClient
from src.api.endpoints import CgyyEndpoints
from src.utils.sign_utils import params_to_sign_parts
from src.utils.time_utils import current_timestamp_ms


@dataclass
class CatalogApi:
    client: ApiClient

    def website_init(self) -> Dict[str, Any]:
        """获取场地信息，不需要登录"""
        ts = current_timestamp_ms()
        params = {
            "catalogSite": 0,
            "indexPictureSize": 10,
            "articleSize": 6,
            "venueForSiteSize": 5,
            "sportSize": 8,
            "hotSiteSize": 10,
            "nocache": ts,
        }
        sign_parts = params_to_sign_parts(params)
        return self.client.get(CgyyEndpoints.WEBSITE_INIT, params=params, sign_parts=sign_parts)

    def website_probe(self) -> Dict[str, Any]:
        """获取预定须知，需要登陆，可用于探测登录是否有效"""
        ts = current_timestamp_ms()
        params = {
            "nocache": ts,
        }
        sign_parts = params_to_sign_parts(params)
        return self.client.get(CgyyEndpoints.WEBSITE_PROBE, params=params, sign_parts=sign_parts)