from __future__ import annotations


class CgyyEndpoints:
    CAPTCHA_GET = "/api/captcha/get"
    CAPTCHA_CHECK = "/api/captcha/check"

    WEBSITE_INIT = "/api/front/website/init"

    RESERVATION_DAY_INFO = "/api/reservation/day/info"
    RESERVATION_SUBMIT = "/api/reservation/order/submit"

    AUTH_LOGIN = "/api/login"
    ROLE_LOGIN = "/roleLogin"

    ORDER_DETAIL = "/api/venue/finances/order/detail"
    ORDER_CANCEL = "/api/venue/finances/order/cancel"
    ORDER_PAY = "/api/venue/finances/order/pay"


class CashierEndpoints:
    TRANSACTION = "/transaction"
    PAY_WAYS = "/api/pay_ways"
    TRANSACTION_PAY = "/transaction/pay"
