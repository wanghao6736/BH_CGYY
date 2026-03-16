from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from src.api.captcha_api import CaptchaApi
from src.api.catalog_api import CatalogApi
from src.api.client import ApiClient
from src.api.reservation_api import ReservationApi
from src.auth.manager import AuthManager
from src.cli.commands import get_cmd
from src.cli.commands import run as run_command
from src.cli.parser import build_parser
from src.cli.validators import CliValidationError, validate_and_normalize_args
from src.config.settings import (ApiSettings, AuthSettings, SsoSettings,
                                 UserSettings, load_settings)
from src.core.captcha_service import CaptchaService
from src.core.catalog_service import CatalogService
from src.core.reservation_service import ReservationService
from src.core.workflow import ReservationWorkflow
from src.presenters.format import format_request_result
from src.utils.crypto_utils import AesCbcEncryptor
from src.utils.sign_utils import SignBuilder

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt)
    root = logging.getLogger()
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    fh = logging.FileHandler(log_dir / "cgyy.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(fh)


def merge_cli_overrides(
    args: Namespace,
    api_settings: ApiSettings,
    user_settings: UserSettings,
) -> None:
    """将 CLI 参数合并到 settings 中。优先级：CLI > .env/环境变量 > 默认值。"""
    cmd = get_cmd(args)

    if args.date:
        api_settings.default_search_date = args.date
        user_settings.reservation_date = args.date
        user_settings.week_start_date = args.date

    if args.start_time:
        user_settings.reservation_start_time = args.start_time
    elif cmd in ("info", "reserve"):
        user_settings.reservation_start_time = ""

    if args.duration is not None:
        user_settings.reservation_slot_count = args.duration
    elif cmd in ("info", "reserve"):
        user_settings.reservation_slot_count = 1

    if args.venue_site_id is not None and args.venue_site_id != -1:
        api_settings.venue_site_id = args.venue_site_id

    if args.buddies:
        user_settings.buddy_ids = args.buddies

    if getattr(args, "strategy", None):
        user_settings.selection_strategy = args.strategy


def build_app(
    api_settings: ApiSettings | None = None,
    user_settings: UserSettings | None = None,
    auth_settings: AuthSettings | None = None,
    sso_settings: SsoSettings | None = None,
    ensure_auth: bool = True,
) -> tuple[ReservationWorkflow, CatalogService]:
    if (
        api_settings is None
        or user_settings is None
        or auth_settings is None
        or sso_settings is None
    ):
        _api, _user, _auth, _sso = load_settings()
        if api_settings is None:
            api_settings = _api
        if user_settings is None:
            user_settings = _user
        if auth_settings is None:
            auth_settings = _auth
        if sso_settings is None:
            sso_settings = _sso

    if ensure_auth:
        auth_manager = AuthManager(api_settings, auth_settings, sso_settings)
        auth_manager.ensure_cgyy_auth()

    sign_builder = SignBuilder(prefix=api_settings.prefix)
    client = ApiClient(
        api_settings=api_settings,
        auth_settings=auth_settings,
        sign_builder=sign_builder,
        retry_count=api_settings.retry_count,
        retry_interval_sec=api_settings.retry_interval_sec,
    )
    captcha_api = CaptchaApi(client=client)
    reservation_api = ReservationApi(
        client=client, api_settings=api_settings, user_settings=user_settings
    )
    catalog_api = CatalogApi(client=client)
    catalog_service = CatalogService(api=catalog_api)
    order_pin_encryptor = AesCbcEncryptor(
        key=api_settings.aes_cbc_key.encode("utf-8"),
        iv=api_settings.aes_cbc_iv.encode("utf-8"),
    )
    captcha_service = CaptchaService(api=captcha_api)
    reservation_service = ReservationService(
        api=reservation_api,
        api_settings=api_settings,
        user_settings=user_settings,
        order_pin_encryptor=order_pin_encryptor,
    )
    workflow = ReservationWorkflow(
        captcha_service=captcha_service,
        reservation_service=reservation_service,
        delay_min=api_settings.captcha_delay_min,
        delay_max=api_settings.captcha_delay_max,
        api_settings=api_settings,
        user_settings=user_settings,
    )
    return workflow, catalog_service


def main() -> None:
    _setup_logging()

    parser = build_parser()
    args = parser.parse_args()

    try:
        args = validate_and_normalize_args(args)
    except CliValidationError as e:
        logger.error("参数错误: %s", e)
        print(format_request_result("参数检查", False, str(e)))
        return

    api_settings, user_settings, auth_settings, sso_settings = load_settings()
    merge_cli_overrides(args, api_settings, user_settings)
    auth_manager = AuthManager(api_settings, auth_settings, sso_settings)
    cmd = get_cmd(args)
    workflow = None
    catalog_service = None
    if cmd not in ("login", "auth-status", "logout"):
        workflow, catalog_service = build_app(
            api_settings,
            user_settings,
            auth_settings,
            sso_settings,
            ensure_auth=True,
        )

    if cmd in ("order-detail", "cancel-order") and not args.trade_no:
        print("❌ 请指定 --trade-no 订单编号")
        return

    run_command(workflow, catalog_service, auth_manager, args)


if __name__ == "__main__":
    main()
