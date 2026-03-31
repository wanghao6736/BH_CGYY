"""CAS 登录页解析。尽量用宽松规则兼容不同页面模板。"""

from __future__ import annotations

import html
import re
from typing import Dict, Optional
from urllib.parse import urljoin, urlsplit

from src.sso.models import CaptchaChallenge, LoginPageContext

_FORM_RE = re.compile(r"<form\b[^>]*action=[\"']?([^\"'>\s]+)[^>]*>(.*?)</form>", re.I | re.S)
_INPUT_RE = re.compile(r"<input\b([^>]*)>", re.I | re.S)
_IMG_RE = re.compile(r"<img\b([^>]*)>", re.I | re.S)
_ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*([\"'])(.*?)\2", re.S)
_TEXT_ERROR_PATTERNS = [
    r"<span[^>]*class=[\"'][^\"']*(?:error|errors|alert-danger|msg-error)[^\"']*[\"'][^>]*>(.*?)</span>",
    r"<div[^>]*class=[\"'][^\"']*(?:error|errors|alert-danger|msg-error)[^\"']*[\"'][^>]*>(.*?)</div>",
    r"<p[^>]*class=[\"'][^\"']*(?:error|errors|alert-danger|msg-error)[^\"']*[\"'][^>]*>(.*?)</p>",
]


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip()


def _parse_attrs(tag_attrs: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for name, _, value in _ATTR_RE.findall(tag_attrs):
        attrs[name.lower()] = html.unescape(value)
    return attrs


def _extract_form(html_text: str) -> tuple[str, str]:
    m = _FORM_RE.search(html_text or "")
    if not m:
        return "", ""
    return html.unescape(m.group(1) or ""), m.group(2) or ""


def _extract_inputs(form_html: str) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    for m in _INPUT_RE.finditer(form_html or ""):
        attrs = _parse_attrs(m.group(1) or "")
        name = attrs.get("name")
        if name:
            result[name] = attrs
    return result


def extract_login_error(html_text: str) -> str:
    for pattern in _TEXT_ERROR_PATTERNS:
        m = re.search(pattern, html_text or "", re.I | re.S)
        if m:
            msg = _strip_tags(m.group(1))
            if msg:
                return msg
    text = _strip_tags(html_text)
    for key in ("用户名或密码错误", "密码错误", "账号或密码错误", "验证码错误"):
        if key in text:
            return key
    return ""


def is_login_page(html_text: str) -> bool:
    text = html_text or ""
    return ("execution" in text and "password" in text) or "casLoginForm" in text


def _is_hidden_attrs(attrs: Dict[str, str]) -> bool:
    style = (attrs.get("style") or "").replace(" ", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return True
    if attrs.get("type", "").lower() == "hidden":
        return True
    if "hidden" in attrs:
        return True
    classes = (attrs.get("class") or "").lower().split()
    return any(name in ("hidden", "sr-only", "d-none") for name in classes)


def _find_visible_captcha_input(inputs: Dict[str, Dict[str, str]]) -> tuple[bool, str]:
    for name, attrs in inputs.items():
        if _is_hidden_attrs(attrs):
            continue
        marker = " ".join(
            [
                name.lower(),
                attrs.get("id", "").lower(),
                attrs.get("class", "").lower(),
                attrs.get("placeholder", "").lower(),
            ]
        )
        if "captcha" in marker or "验证码" in marker:
            return True, name
    return False, ""


def detect_captcha(html_text: str, page_url: str) -> Optional[CaptchaChallenge]:
    text = html_text or ""
    form_action, form_html = _extract_form(text)
    del form_action
    inputs = _extract_inputs(form_html or text)
    input_found, field_name = _find_visible_captcha_input(inputs)

    image_url = ""
    image_found = False
    for m in _IMG_RE.finditer(form_html or text):
        attrs = _parse_attrs(m.group(1) or "")
        if _is_hidden_attrs(attrs):
            continue
        src = attrs.get("src", "")
        marker = " ".join(
            [
                src.lower(),
                attrs.get("id", "").lower(),
                attrs.get("class", "").lower(),
                attrs.get("alt", "").lower(),
            ]
        )
        if "captcha" not in marker and "验证码" not in marker:
            continue
        if not src:
            continue
        image_url = urljoin(page_url, html.unescape(src))
        image_found = True
        break

    if not input_found and not image_found:
        return None
    return CaptchaChallenge(
        image_url=image_url,
        field_name=field_name or "captcha",
    )


def parse_login_page(html_text: str, page_url: str) -> LoginPageContext:
    action, form_html = _extract_form(html_text)
    inputs = _extract_inputs(form_html)
    hidden_fields = {
        name: attrs.get("value", "")
        for name, attrs in inputs.items()
        if attrs.get("type", "").lower() in ("hidden", "submit", "")
        and name not in ("username", "password", "captcha")
    }
    username_field = "username"
    password_field = "password"
    for name, attrs in inputs.items():
        typ = attrs.get("type", "").lower()
        if typ == "password":
            password_field = name
        elif typ in ("text", "") and ("user" in name.lower() or "name" == name.lower()):
            username_field = name
    captcha = detect_captcha(html_text, page_url)
    lowered = (html_text or "").lower()
    is_continue_page = "ignoreandcontinue" in lowered or "continue" in lowered and "password" not in lowered
    form_action = urljoin(page_url, action or "")
    if form_action:
        page_parts = urlsplit(page_url)
        action_parts = urlsplit(form_action)
        if (
            action_parts.scheme == page_parts.scheme
            and action_parts.netloc == page_parts.netloc
            and action_parts.path == page_parts.path
            and not action_parts.query
            and page_parts.query
        ):
            form_action = page_url
    return LoginPageContext(
        page_url=page_url,
        form_action=form_action,
        hidden_fields=hidden_fields,
        username_field=username_field,
        password_field=password_field,
        captcha_required=captcha is not None,
        captcha_challenge=captcha,
        error_message=extract_login_error(html_text),
        is_login_page=is_login_page(html_text),
        is_continue_page=is_continue_page,
    )
