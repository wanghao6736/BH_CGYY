from __future__ import annotations

from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Dict, Optional


@dataclass
class AuthContext:
    cookies: Dict[str, str] = field(default_factory=dict)
    cg_authorization: str = ""

    @classmethod
    def from_cookie_header(
        cls, cookie_header: str = "", cg_authorization: str = ""
    ) -> "AuthContext":
        jar = SimpleCookie()
        cookies: Dict[str, str] = {}
        if cookie_header:
            try:
                jar.load(cookie_header)
            except Exception:
                jar = SimpleCookie()
            for key, morsel in jar.items():
                cookies[key] = morsel.value
        return cls(cookies=cookies, cg_authorization=cg_authorization)

    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def get_cookie(self, name: str) -> str:
        return self.cookies.get(name, "")


@dataclass
class ServiceAuthState:
    service_name: str
    cookie: str = ""
    cg_authorization: str = ""
    obtained_at: float = 0.0
    source: str = ""

    def to_auth_context(self) -> AuthContext:
        return AuthContext.from_cookie_header(self.cookie, self.cg_authorization)


@dataclass
class AuthBootstrapResult:
    reused: bool
    refreshed: bool
    state: Optional[ServiceAuthState]
