import os
from dataclasses import dataclass
from datetime import date
from typing import Tuple

from src.api.endpoints import CgyyEndpoints, SsoEndpoints
from src.config.env_store import EnvStore
from src.config.profiles import build_env_store, normalize_profile_name


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


@dataclass
class ApiSettings:
    base_url: str = CgyyEndpoints.BASE_URL
    prefix: str = ""
    app_key: str = ""
    aes_cbc_key: str = ""
    aes_cbc_iv: str = ""
    venue_site_id: int = 57
    default_search_date: str = ""  # 使用当天，接口支持三天内含当天
    # 验证码获取与校验之间的延迟区间（秒）
    captcha_delay_min: float = 1.0
    captcha_delay_max: float = 2.5
    # 请求失败重试
    retry_count: int = 5
    retry_interval_sec: float = 2.0


@dataclass
class UserSettings:
    profile_name: str = "default"
    display_name: str = ""
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
    login_base_url: str = f"{SsoEndpoints.DOMAIN}{SsoEndpoints.LOGIN_ENTRY}"
    service_url: str = f"{CgyyEndpoints.BASE_URL}{CgyyEndpoints.SSO_LOGIN}"
    username: str = ""
    password: str = ""
    max_redirects: int = 10
    timeout_sec: float = 10.0
    persist_to_env: bool = True


def load_settings(
    profile_name: str | None = None,
    env_store: EnvStore | None = None,
) -> Tuple[ApiSettings, UserSettings, AuthSettings, SsoSettings]:
    env = env_store or build_env_store(profile_name, environ=dict(os.environ))
    active_profile = normalize_profile_name(profile_name, env.environ)

    api = ApiSettings(
        base_url=env.get_str("CGYY_BASE_URL", ApiSettings.base_url),
        prefix=env.get_str("CGYY_PREFIX", ApiSettings.prefix),
        app_key=env.get_str("CGYY_APP_KEY", ApiSettings.app_key),
        venue_site_id=env.get_int("CGYY_VENUE_SITE_ID", ApiSettings.venue_site_id),
        default_search_date=env.get_str("CGYY_DEFAULT_SEARCH_DATE", ApiSettings.default_search_date),
        aes_cbc_key=env.get_str("CGYY_AES_CBC_KEY", ApiSettings.aes_cbc_key),
        aes_cbc_iv=env.get_str("CGYY_AES_CBC_IV", ApiSettings.aes_cbc_iv),
    )
    user = UserSettings(
        profile_name=active_profile,
        display_name=env.get_str("CGYY_DISPLAY_NAME", ""),
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
    )
    return api, user, auth, sso
