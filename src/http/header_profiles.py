from __future__ import annotations

from typing import Mapping

JSON_ACCEPT = "application/json, text/plain, */*"
HTML_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
FORM_URLENCODED_CONTENT_TYPE = "application/x-www-form-urlencoded"

GENERIC_BROWSER_USER_AGENT = "Mozilla/5.0"
DESKTOP_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
CASHIER_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "wxworklocal/3.3.0 wxwork/4.0.0 MicroMessenger/7.0.1 "
    "appname/wxworklocal-customized wwlocal/3.3.0 "
    "appscheme/buaawx.cc-pay.cn Language/zh_CN WXWorklocalClientType/IOS"
)


def _apply_extra_headers(
    headers: dict[str, str],
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if extra_headers:
        headers.update({str(key): str(value) for key, value in extra_headers.items()})
    return headers


def build_api_form_headers(
    *,
    user_agent: str = GENERIC_BROWSER_USER_AGENT,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    return _apply_extra_headers(
        {
            "accept": JSON_ACCEPT,
            "user-agent": user_agent,
            "content-type": FORM_URLENCODED_CONTENT_TYPE,
        },
        extra_headers,
    )


def build_page_headers(
    *,
    referer: str = "",
    user_agent: str = DESKTOP_BROWSER_USER_AGENT,
    accept: str = HTML_ACCEPT,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": user_agent,
    }
    if referer:
        headers["Referer"] = referer
    return _apply_extra_headers(headers, extra_headers)


def build_form_post_headers(
    *,
    user_agent: str = DESKTOP_BROWSER_USER_AGENT,
    referer: str = "",
    accept: str = HTML_ACCEPT,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    headers = build_page_headers(
        referer=referer,
        user_agent=user_agent,
        accept=accept,
    )
    headers["content-type"] = FORM_URLENCODED_CONTENT_TYPE
    return _apply_extra_headers(headers, extra_headers)


def build_cashier_headers(
    *,
    referer: str,
    accept: str,
    user_agent: str = DESKTOP_BROWSER_USER_AGENT,
    version: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    headers = build_page_headers(
        referer=referer,
        user_agent=user_agent,
        accept=accept,
    )
    if version is not None:
        headers["version"] = version
    return _apply_extra_headers(headers, extra_headers)
