from dataclasses import dataclass
from datetime import date
from typing import Tuple

from src.config.env_store import EnvStore


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


@dataclass
class ApiSettings:
    base_url: str = ""
    prefix: str = ""
    app_key: str = ""
    # AES-CBC 加密所需 key/iv，通过环境变量设置
    aes_cbc_key: str = ""
    aes_cbc_iv: str = ""
    venue_site_id: int = 57
    default_search_date: str = ""  # 使用当天，接口支持三天内含当天
    # 验证码获取与校验之间的延迟区间（秒）
    captcha_delay_min: float = 1.0
    captcha_delay_max: float = 2.5
    # 请求失败重试
    retry_count: int = 3
    retry_interval_sec: float = 2.0


@dataclass
class UserSettings:
    phone: str = ""
    buddy_ids: str = ""
    reservation_date: str = ""
    reservation_order_json: str = ""
    reservation_type: str = ""
    week_start_date: str = ""
    # orderPin 随机范围
    order_pin_x_min: int = 1000
    order_pin_x_max: int = 1150
    order_pin_y_min: int = 600
    order_pin_y_max: int = 700
    order_price: float = 50.0
    reservation_start_time: str = ""
    reservation_slot_count: int = 2
    selection_strategy: str = "same_first_digit,same_venue,cheapest"


@dataclass
class AuthSettings:
    cookie: str = ""
    cg_authorization: str = ""


@dataclass
class SsoSettings:
    enabled: bool = False
    login_base_url: str = ""
    service_url: str = ""
    username: str = ""
    password: str = ""
    max_redirects: int = 10
    timeout_sec: float = 10.0
    persist_to_env: bool = True


def load_settings() -> Tuple[ApiSettings, UserSettings, AuthSettings, SsoSettings]:
    env = EnvStore()

    api = ApiSettings(
        base_url=env.get_str("CGYY_BASE_URL", ApiSettings.base_url),
        prefix=env.get_str("CGYY_PREFIX", ApiSettings.prefix),
        app_key=env.get_str("CGYY_APP_KEY", ApiSettings.app_key),
        venue_site_id=env.get_int("CGYY_VENUE_SITE_ID", ApiSettings.venue_site_id),
        default_search_date=env.get_str("CGYY_DEFAULT_SEARCH_DATE", ApiSettings.default_search_date),
        aes_cbc_key=env.get_str("CGYY_AES_CBC_KEY", ApiSettings.aes_cbc_key),
        aes_cbc_iv=env.get_str("CGYY_AES_CBC_IV", ApiSettings.aes_cbc_iv),
        captcha_delay_min=env.get_float("CGYY_CAPTCHA_DELAY_MIN", ApiSettings.captcha_delay_min),
        captcha_delay_max=env.get_float("CGYY_CAPTCHA_DELAY_MAX", ApiSettings.captcha_delay_max),
        retry_count=env.get_int("CGYY_RETRY_COUNT", ApiSettings.retry_count),
        retry_interval_sec=env.get_float("CGYY_RETRY_INTERVAL_SEC", ApiSettings.retry_interval_sec),
    )
    user = UserSettings(
        phone=env.get_str("CGYY_PHONE", UserSettings.phone),
        buddy_ids=env.get_str("CGYY_BUDDY_IDS", UserSettings.buddy_ids),
        reservation_date=_today_str(),
        reservation_order_json=env.get_str(
            "CGYY_RESERVATION_ORDER_JSON", UserSettings.reservation_order_json
        ),
        reservation_type=env.get_str("CGYY_RESERVATION_TYPE", UserSettings.reservation_type),
        week_start_date=api.default_search_date or _today_str(),
        reservation_start_time=env.get_str("CGYY_RESERVATION_START_TIME", UserSettings.reservation_start_time),
        reservation_slot_count=env.get_int(
            "CGYY_RESERVATION_SLOT_COUNT", UserSettings.reservation_slot_count),
        order_pin_x_min=env.get_int("CGYY_ORDER_PIN_X_MIN", UserSettings.order_pin_x_min),
        order_pin_x_max=env.get_int("CGYY_ORDER_PIN_X_MAX", UserSettings.order_pin_x_max),
        order_pin_y_min=env.get_int("CGYY_ORDER_PIN_Y_MIN", UserSettings.order_pin_y_min),
        order_pin_y_max=env.get_int("CGYY_ORDER_PIN_Y_MAX", UserSettings.order_pin_y_max),
        order_price=UserSettings.order_price,
        selection_strategy=env.get_str(
            "CGYY_SELECTION_STRATEGY", UserSettings.selection_strategy
        ),
    )
    cookie = env.get_str("CGYY_COOKIE", AuthSettings.cookie)
    cg_auth = env.get_str("CGYY_CG_AUTH", AuthSettings.cg_authorization)
    auth = AuthSettings(cookie=cookie, cg_authorization=cg_auth)
    sso = SsoSettings(
        enabled=env.get_bool("CGYY_SSO_ENABLED", SsoSettings.enabled),
        login_base_url=env.get_str("CGYY_SSO_LOGIN_URL", SsoSettings.login_base_url),
        service_url=env.get_str("CGYY_SSO_SERVICE_URL", SsoSettings.service_url),
        username=env.get_str("CGYY_SSO_USERNAME", SsoSettings.username),
        password=env.get_str("CGYY_SSO_PASSWORD", SsoSettings.password),
        max_redirects=env.get_int("CGYY_SSO_MAX_REDIRECTS", SsoSettings.max_redirects),
        timeout_sec=env.get_float("CGYY_SSO_TIMEOUT_SEC", SsoSettings.timeout_sec),
        persist_to_env=env.get_bool("CGYY_AUTH_PERSIST_TO_ENV", SsoSettings.persist_to_env),
    )
    return api, user, auth, sso
