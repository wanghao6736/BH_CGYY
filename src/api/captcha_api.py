from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict

from src.api.client import ApiClient
from src.utils.sign_utils import params_to_sign_parts
from src.utils.time_utils import current_timestamp_ms

REL_GET = "/api/captcha/get"
REL_CHECK = "/api/captcha/check"
CAPTCHA_TYPE = "clickWord"


@dataclass
class CaptchaApi:
    client: ApiClient

    def generate_client_uid(self) -> str:
        return "point-" + str(uuid.uuid4())

    def get_captcha_raw(self) -> Dict[str, Any]:
        client_uid = self.generate_client_uid()
        ts = current_timestamp_ms()
        params = {
            "captchaType": CAPTCHA_TYPE,
            "clientUid": client_uid,
            "nocache": ts,
            "ts": ts,
        }
        sign_parts = params_to_sign_parts(params)
        return self.client.get(REL_GET, params=params, sign_parts=sign_parts)

    def check_captcha(self, point_json: str, token: str) -> Dict[str, Any]:
        data = {
            "captchaType": CAPTCHA_TYPE,
            "pointJson": point_json,
            "token": token,
        }
        sign_parts = params_to_sign_parts(data)
        return self.client.post(REL_CHECK, data=data, sign_parts=sign_parts)
