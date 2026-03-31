from urllib.parse import quote

from src.api.cashier_api import CashierApi
from src.http.header_profiles import CASHIER_MOBILE_USER_AGENT


class _FakeCashierClient:
    def __init__(self) -> None:
        self.json_calls: list[tuple[str, str, str | None]] = []
        self.text_calls: list[tuple[str, str, str | None]] = []

    def get_json(
        self,
        rel_path_or_url: str,
        *,
        referer: str,
        version: str | None = "v2",
        extra_headers: dict | None = None,
    ) -> dict:
        self.json_calls.append((rel_path_or_url, referer, version))
        return {}

    def get_text(
        self,
        rel_path_or_url: str,
        *,
        referer: str,
        version: str | None = None,
        user_agent: str | None = None,
        extra_headers: dict | None = None,
    ) -> str:
        self.text_calls.append((rel_path_or_url, referer, user_agent))
        return "<html></html>"


def test_get_transaction_builds_expected_path() -> None:
    client = _FakeCashierClient()
    api = CashierApi(client=client)  # type: ignore[arg-type]
    api.get_transaction("cashier-1", "https://cashier.cc-pay.cn/cashier?id=cashier-1")
    path, referer, version = client.json_calls[0]
    assert path.startswith("/transaction?_t==")
    assert path.endswith("&id=cashier-1")
    assert referer == "https://cashier.cc-pay.cn/cashier?id=cashier-1"
    assert version == "v2"


def test_pay_builds_expected_path() -> None:
    client = _FakeCashierClient()
    api = CashierApi(client=client)  # type: ignore[arg-type]
    api.pay("cashier-1", "way-2", "https://cashier.cc-pay.cn/cashier?id=cashier-1")
    path, referer, _ = client.json_calls[0]
    assert path.startswith("/transaction/pay?_t==")
    assert "&id=cashier-1" in path
    assert "&payWayId=way-2" in path
    assert "&phoneNumber=&ecCode=" in path
    assert referer.endswith("id=cashier-1")


def test_fetch_wap_page_appends_redirect_url() -> None:
    client = _FakeCashierClient()
    api = CashierApi(client=client)  # type: ignore[arg-type]
    api.fetch_wap_page(
        "https://wx.tenpay.com/checkmweb?prepay_id=abc",
        cashier_origin="https://cashier.cc-pay.cn",
        cashier_id="cashier-1",
        referer="https://cashier.cc-pay.cn/cashier?id=cashier-1",
    )
    request_url, referer, user_agent = client.text_calls[0]
    encoded_redirect = quote(
        "https://cashier.cc-pay.cn/cashier?id=cashier-1&for=wxpay_wap",
        safe="",
    )
    assert request_url.endswith(f"&redirect_url={encoded_redirect}")
    assert referer.endswith("id=cashier-1")
    assert user_agent == CASHIER_MOBILE_USER_AGENT
