from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Credentials:
    username: str
    password: str
    captcha: str = ""


@dataclass
class PageResponse:
    url: str
    status_code: int
    headers: Dict[str, str]
    text: str

    @property
    def location(self) -> str:
        return self.headers.get("Location") or self.headers.get("location") or ""


@dataclass
class CaptchaChallenge:
    image_url: str = ""
    field_name: str = "captcha"


@dataclass
class LoginPageContext:
    page_url: str
    form_action: str
    hidden_fields: Dict[str, str] = field(default_factory=dict)
    username_field: str = "username"
    password_field: str = "password"
    captcha_required: bool = False
    captcha_challenge: Optional[CaptchaChallenge] = None
    error_message: str = ""
    is_login_page: bool = True
    is_continue_page: bool = False


@dataclass
class RedirectStep:
    request_url: str
    status_code: int
    location: str = ""


@dataclass
class SsoLoginResult:
    success: bool
    message: str
    final_url: str
    redirect_chain: List[RedirectStep] = field(default_factory=list)
    cookies: Dict[str, str] = field(default_factory=dict)
