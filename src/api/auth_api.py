from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.api.client import ApiClient
from src.api.endpoints import CgyyEndpoints
from src.utils.sign_utils import params_to_sign_parts


@dataclass
class AuthApi:
    client: ApiClient

    def login_with_sso_token(self, sso_token: str) -> Dict[str, Any]:
        return self.client.post(
            CgyyEndpoints.AUTH_LOGIN,
            data={},
            sign_parts=[],
            extra_headers={"sso-token": sso_token},
        )

    def role_login(self, role_id: int, cg_authorization: str) -> Dict[str, Any]:
        data = {"roleid": role_id}
        return self.client.post(
            CgyyEndpoints.ROLE_LOGIN,
            data=data,
            sign_parts=params_to_sign_parts(data),
            extra_headers={"cgAuthorization": cg_authorization},
        )
