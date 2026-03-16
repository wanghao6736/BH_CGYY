"""业务鉴权接口解析。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.parsers.common import get_by_path, parse_success_message


@dataclass
class RoleItem:
    id: int
    name: str
    role_type: int = 0


@dataclass
class AuthTokenParsed:
    access_token: str
    roles: List[RoleItem]


def _parse_roles(resp: Dict[str, Any]) -> List[RoleItem]:
    raw_roles = (
        get_by_path(resp, "data.roles")
        or get_by_path(resp, "data.roleList")
        or get_by_path(resp, "data.token.roles")
        or []
    )
    if not isinstance(raw_roles, list):
        return []
    roles: List[RoleItem] = []
    for item in raw_roles:
        if not isinstance(item, dict):
            continue
        role_id = item.get("id")
        if role_id is None:
            continue
        roles.append(
            RoleItem(
                id=int(role_id),
                name=str(item.get("name") or ""),
                role_type=int(item.get("roleType") or 0),
            )
        )
    return roles


def parse_auth_token_response(resp: Dict[str, Any]) -> tuple[bool, str, Optional[AuthTokenParsed]]:
    success, message = parse_success_message(resp)
    access_token = get_by_path(resp, "data.token.access_token")
    if not success or not access_token:
        return success, message, None
    return (
        success,
        message,
        AuthTokenParsed(
            access_token=str(access_token),
            roles=_parse_roles(resp),
        ),
    )
