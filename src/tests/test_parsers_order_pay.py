from src.parsers.order import parse_order_pay_data, parse_order_pay_response


def test_parse_order_pay_data() -> None:
    data = {
        "schoolPayUrl": "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
    }
    parsed = parse_order_pay_data(data)
    assert parsed is not None
    assert parsed.school_pay_url.endswith("id=abc123&channel=BUAASSO")


def test_parse_order_pay_response() -> None:
    resp = {
        "code": 200,
        "data": {
            "schoolPayUrl": "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO",
        },
    }
    ok, msg, parsed = parse_order_pay_response(resp)
    assert ok is True
    assert msg == ""
    assert parsed is not None
    assert parsed.school_pay_url.startswith("https://cashier.cc-pay.cn/cashier")
