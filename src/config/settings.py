import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Tuple


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


def _load_dotenv_if_exists() -> None:
    """
    从项目根目录的 .env 加载环境变量（KEY=VALUE 形式，# 开头为注释）
    """
    root = Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def load_settings() -> Tuple[ApiSettings, UserSettings, AuthSettings]:
    # 优先从 .env 加载，再读取 os.environ
    _load_dotenv_if_exists()

    api = ApiSettings(
        base_url=os.getenv("CGYY_BASE_URL", ApiSettings.base_url),
        prefix=os.getenv("CGYY_PREFIX", ApiSettings.prefix),
        app_key=os.getenv("CGYY_APP_KEY", ApiSettings.app_key),
        venue_site_id=int(os.getenv("CGYY_VENUE_SITE_ID", str(ApiSettings.venue_site_id))),
        default_search_date=os.getenv("CGYY_DEFAULT_SEARCH_DATE", ApiSettings.default_search_date),
        aes_cbc_key=os.getenv("CGYY_AES_CBC_KEY", ApiSettings.aes_cbc_key),
        aes_cbc_iv=os.getenv("CGYY_AES_CBC_IV", ApiSettings.aes_cbc_iv),
        captcha_delay_min=float(os.getenv("CGYY_CAPTCHA_DELAY_MIN", str(ApiSettings.captcha_delay_min))),
        captcha_delay_max=float(os.getenv("CGYY_CAPTCHA_DELAY_MAX", str(ApiSettings.captcha_delay_max))),
        retry_count=int(os.getenv("CGYY_RETRY_COUNT", str(ApiSettings.retry_count))),
        retry_interval_sec=float(os.getenv("CGYY_RETRY_INTERVAL_SEC", str(ApiSettings.retry_interval_sec))),
    )
    user = UserSettings(
        phone=os.getenv("CGYY_PHONE", UserSettings.phone),
        buddy_ids=os.getenv("CGYY_BUDDY_IDS", UserSettings.buddy_ids),
        reservation_date=_today_str(),
        reservation_order_json=os.getenv(
            "CGYY_RESERVATION_ORDER_JSON", UserSettings.reservation_order_json
        ),
        reservation_type=os.getenv("CGYY_RESERVATION_TYPE", UserSettings.reservation_type),
        week_start_date=api.default_search_date or _today_str(),
        reservation_start_time=os.getenv("CGYY_RESERVATION_START_TIME", UserSettings.reservation_start_time),
        reservation_slot_count=int(
            os.getenv(
                "CGYY_RESERVATION_SLOT_COUNT", str(
                    UserSettings.reservation_slot_count))),
        order_pin_x_min=int(os.getenv("CGYY_ORDER_PIN_X_MIN", UserSettings.order_pin_x_min)),
        order_pin_x_max=int(os.getenv("CGYY_ORDER_PIN_X_MAX", UserSettings.order_pin_x_max)),
        order_pin_y_min=int(os.getenv("CGYY_ORDER_PIN_Y_MIN", UserSettings.order_pin_y_min)),
        order_pin_y_max=int(os.getenv("CGYY_ORDER_PIN_Y_MAX", UserSettings.order_pin_y_max)),
        order_price=UserSettings.order_price,
        selection_strategy=os.getenv(
            "CGYY_SELECTION_STRATEGY", UserSettings.selection_strategy
        ),
    )
    cookie = os.getenv("CGYY_COOKIE", AuthSettings.cookie)
    cg_auth = os.getenv("CGYY_CG_AUTH", AuthSettings.cg_authorization)
    auth = AuthSettings(cookie=cookie, cg_authorization=cg_auth)
    return api, user, auth
