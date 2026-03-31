from types import SimpleNamespace

from requests.cookies import RequestsCookieJar

from src.auth.cashier_auth_service import CashierBootstrapService
from src.auth.exceptions import CashierBootstrapError
from src.config.settings import BUAA_CGYY_REFERER, SsoSettings
from src.sso.models import PageResponse


class _FakePageClient:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self._session = SimpleNamespace(cookies=RequestsCookieJar(), headers={})
        self.calls: list[tuple[str, dict]] = []

    def get_page(self, url: str, params=None, headers=None) -> PageResponse:
        self.calls.append((url, headers or {}))
        current = self._responses.pop(0)
        for name, value in current.get("set_cookies", {}).items():
            self._session.cookies.set(name, value)
        return PageResponse(
            url=url,
            status_code=current["status_code"],
            headers=current.get("headers", {}),
            text=current.get("text", ""),
        )

    def cookies_dict(self) -> dict[str, str]:
        return self._session.cookies.get_dict()


class _TestCashierBootstrapService(CashierBootstrapService):
    def __init__(self, page_client: _FakePageClient, sso_settings: SsoSettings | None = None) -> None:
        super().__init__(sso_settings=sso_settings or SsoSettings())
        self._page_client = page_client

    def _build_page_client(self, cookie_header: str = "") -> _FakePageClient:
        return self._page_client


def test_build_page_client_seeds_all_cookie_values() -> None:
    service = CashierBootstrapService()

    page_client = service._build_page_client(
        "CASTGC=castgc-1; JSESSIONID=jsession-1; sso_buaa_token=token-1"
    )

    assert page_client.cookies_dict()["CASTGC"] == "castgc-1"
    assert page_client.cookies_dict()["JSESSIONID"] == "jsession-1"
    assert page_client.cookies_dict()["sso_buaa_token"] == "token-1"


def test_bootstrap_from_school_pay_url_follows_sso_redirects_automatically() -> None:
    page_client = _FakePageClient(
        [
            {
                "status_code": 302,
                "headers": {"Location": "https://pass.cc-pay.cn/login?backUrl=foo"},
                "set_cookies": {"connect.sid": "sid-1"},
            },
            {
                "status_code": 302,
                "headers": {"Location": "https://sso.buaa.edu.cn/login?service=foo"},
            },
            {
                "status_code": 302,
                "headers": {"Location": "https://pass.cc-pay.cn/login?ticket=ST-123"},
            },
            {
                "status_code": 302,
                "headers": {"Location": "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO"},
                "set_cookies": {"user_id": "user-1", "avatar_dir": "avatar-1"},
            },
            {
                "status_code": 200,
                "headers": {},
            },
        ]
    )
    service = _TestCashierBootstrapService(page_client)
    result = service.bootstrap_from_school_pay_url(
        "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO"
    )
    assert result.cookie == "connect.sid=sid-1; user_id=user-1; avatar_dir=avatar-1"
    assert page_client.calls[0][1]["Referer"] == BUAA_CGYY_REFERER


def test_bootstrap_raises_when_entry_has_no_location() -> None:
    page_client = _FakePageClient(
        [
            {
                "status_code": 200,
                "headers": {},
            }
        ]
    )
    service = _TestCashierBootstrapService(page_client)
    try:
        service.bootstrap_from_school_pay_url(
            "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO"
        )
    except CashierBootstrapError as exc:
        assert "未返回跳转地址" in str(exc)
    else:
        raise AssertionError("expected CashierBootstrapError")


def test_bootstrap_raises_clear_error_when_sso_requires_credentials() -> None:
    page_client = _FakePageClient(
        [
            {
                "status_code": 302,
                "headers": {"Location": "https://pass.cc-pay.cn/login?backUrl=foo"},
                "set_cookies": {"connect.sid": "sid-1"},
            },
            {
                "status_code": 302,
                "headers": {"Location": "https://sso.buaa.edu.cn/login?service=https://pass.cc-pay.cn/login"},
            },
            {
                "status_code": 200,
                "headers": {},
                "text": """
                    <html><body>
                    <form action="/login">
                      <input type="hidden" name="execution" value="e1s1" />
                      <input type="text" name="username" />
                      <input type="password" name="password" />
                    </form>
                    </body></html>
                """,
            },
        ]
    )
    service = _TestCashierBootstrapService(page_client, sso_settings=SsoSettings())
    try:
        service.bootstrap_from_school_pay_url(
            "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO"
        )
    except CashierBootstrapError as exc:
        assert "统一认证需要账号密码" in str(exc)
    else:
        raise AssertionError("expected CashierBootstrapError")
