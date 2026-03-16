from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict
from urllib.parse import quote

from src.sso.models import Credentials, LoginPageContext, PageResponse
from src.sso.parsers.cas_parser import parse_login_page

logger = logging.getLogger(__name__)


@dataclass
class CasProvider:
    login_base_url: str
    username_field: str = "username"
    password_field: str = "password"
    execution_field: str = "execution"
    event_id_value: str = "submit"

    def build_login_entry_url(self, service_url: str) -> str:
        base = self.login_base_url.strip()
        if "{service}" in base:
            return base.format(service=quote(service_url, safe=":/?=&%"))
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}service={quote(service_url, safe=':/?=&%')}"

    def parse_login_page(self, resp: PageResponse) -> LoginPageContext:
        context = parse_login_page(resp.text, resp.url)
        logger.info(
            "解析登录页 url=%s login_page=%s continue_page=%s captcha=%s",
            resp.url,
            context.is_login_page,
            context.is_continue_page,
            context.captcha_required,
        )
        return context

    def build_login_form(
        self,
        context: LoginPageContext,
        credentials: Credentials,
    ) -> Dict[str, str]:
        payload = dict(context.hidden_fields)
        payload[context.username_field or self.username_field] = credentials.username
        payload[context.password_field or self.password_field] = credentials.password
        payload.setdefault("_eventId", self.event_id_value)
        if context.captcha_required and credentials.captcha:
            field_name = (
                context.captcha_challenge.field_name
                if context.captcha_challenge
                else "captcha"
            )
            payload[field_name] = credentials.captcha
        return {k: str(v) for k, v in payload.items()}

    def build_continue_form(self, context: LoginPageContext) -> Dict[str, str]:
        payload = dict(context.hidden_fields)
        payload.setdefault("_eventId", "submit")
        payload.setdefault("ignoreAndContinue", "true")
        return {k: str(v) for k, v in payload.items()}
