from src.parsers.cashier import (choose_pay_way, extract_weixin_scheme,
                                 parse_cashier_pay_response,
                                 parse_cashier_pay_ways_response,
                                 parse_cashier_transaction_response,
                                 parse_cashier_url)


def test_parse_cashier_url() -> None:
    parsed = parse_cashier_url(
        "https://cashier.cc-pay.cn/cashier?id=abc123&channel=BUAASSO"
    )
    assert parsed is not None
    assert parsed.origin == "https://cashier.cc-pay.cn"
    assert parsed.cashier_id == "abc123"
    assert parsed.channel == "BUAASSO"


def test_parse_cashier_transaction_response_supports_top_level_success() -> None:
    resp = {
        "success": True,
        "data": {
            "id": "txn-1",
            "goodsId": "goods-9",
            "money": 70,
            "status": 1,
            "subject": "羽毛球",
            "body": "综合馆",
            "targetOrderId": "760907",
            "notifyUrl": "https://notify.example",
            "returnUrl": "https://return.example",
        },
    }
    ok, msg, parsed = parse_cashier_transaction_response(resp)
    assert ok is True
    assert msg == ""
    assert parsed is not None
    assert parsed.transaction_id == "txn-1"
    assert parsed.goods_id == "goods-9"
    assert parsed.money == 70.0
    assert parsed.target_order_id == "760907"


def test_parse_cashier_transaction_response_supports_string_status() -> None:
    resp = {
        "success": True,
        "data": {
            "id": "txn-2",
            "goodsId": "goods-10",
            "money": "35.00",
            "status": "wait_payer_pay",
            "subject": "羽毛球",
            "body": "综合馆",
            "targetOrderId": "760908",
            "notifyUrl": "https://notify.example",
            "returnUrl": "https://return.example",
        },
    }
    ok, msg, parsed = parse_cashier_transaction_response(resp)
    assert ok is True
    assert msg == ""
    assert parsed is not None
    assert parsed.money == 35.0
    assert parsed.status == "wait_payer_pay"


def test_parse_cashier_pay_ways_response_and_choose_pay_way() -> None:
    resp = {
        "success": True,
        "data": {
            "normal": [
                {
                    "id": "way-1",
                    "name": "wxpay_web",
                    "text": "微信扫码支付",
                    "description": "PC",
                },
                {
                    "id": "way-2",
                    "name": "wxpay_wap",
                    "text": "微信 H5 支付",
                    "description": "Mobile",
                },
            ]
        },
    }
    ok, _, parsed = parse_cashier_pay_ways_response(resp)
    selected = choose_pay_way(parsed, "wxpay_wap")
    assert ok is True
    assert parsed is not None
    assert len(parsed.normal) == 2
    assert selected is not None
    assert selected.id == "way-2"
    assert choose_pay_way(parsed, "alipay") is None


def test_parse_cashier_pay_response() -> None:
    resp = {
        "success": True,
        "data": {
            "transactionId": "txn-1",
            "isPaid": False,
            "payUrl": "https://wx.tenpay.com/checkmweb?prepay_id=abc",
            "payQrCode": "weixin://wxpay/bizpayurl?pr=desktop",
            "payWebForm": "",
            "wxpayJsapiDataStr": "",
        },
    }
    ok, _, parsed = parse_cashier_pay_response(resp)
    assert ok is True
    assert parsed is not None
    assert parsed.transaction_id == "txn-1"
    assert parsed.is_paid is False
    assert parsed.pay_qr_code.startswith("weixin://")


def test_extract_weixin_scheme() -> None:
    html = '<html><body><a href="weixin://wap/pay?prepayid=12345">Pay</a></body></html>'
    assert extract_weixin_scheme(html) == "weixin://wap/pay?prepayid=12345"
    assert extract_weixin_scheme("<html></html>") == ""
