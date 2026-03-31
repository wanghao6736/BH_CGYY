from __future__ import annotations

import logging
import os
from argparse import Namespace
from typing import Mapping

from src.api.captcha_api import CaptchaApi
from src.api.catalog_api import CatalogApi
from src.api.client import ApiClient
from src.api.reservation_api import ReservationApi
from src.auth.cashier_auth_service import CashierBootstrapService
from src.auth.manager import AuthManager
from src.cli.commands import get_cmd
from src.cli.commands import run as run_command
from src.cli.context import AppServices, CommandContext
from src.cli.handlers.registry import get_command_kind, requires_trade_no
from src.cli.parser import build_parser
from src.cli.validators import CliValidationError, validate_and_normalize_args
from src.config.profiles import (ProfileManager, build_env_store,
                                 normalize_profile_name)
from src.config.settings import (ApiSettings, AuthSettings, SsoSettings,
                                 UserSettings, load_settings)
from src.core.captcha_service import CaptchaService
from src.core.catalog_service import CatalogService
from src.core.payment_service import PaymentService
from src.core.reservation_service import ReservationService
from src.core.workflow import ReservationWorkflow
from src.logging_setup import setup_logging
from src.presenters.format import format_request_result
from src.utils.crypto_utils import AesCbcEncryptor
from src.utils.sign_utils import SignBuilder

logger = logging.getLogger(__name__)


def merge_cli_overrides(
    args: Namespace,
    api_settings: ApiSettings,
    user_settings: UserSettings,
) -> None:
    """将 CLI 参数合并到 settings 中。优先级：CLI > .env/环境变量 > 默认值。"""
    cmd = get_cmd(args)

    if getattr(args, "date", None):
        api_settings.default_search_date = args.date
        user_settings.reservation_date = args.date
        user_settings.week_start_date = args.date

    if getattr(args, "start_time", None):
        user_settings.reservation_start_time = args.start_time
    elif cmd in ("info", "reserve"):
        user_settings.reservation_start_time = ""

    if getattr(args, "duration", None) is not None:
        user_settings.reservation_slot_count = args.duration
    elif cmd in ("info", "reserve"):
        user_settings.reservation_slot_count = 1

    if getattr(args, "venue_site_id", None) is not None and args.venue_site_id != -1:
        api_settings.venue_site_id = args.venue_site_id

    if getattr(args, "buddies", None):
        user_settings.buddy_ids = args.buddies

    if getattr(args, "strategy", None):
        user_settings.selection_strategy = args.strategy


def build_app(
    api_settings: ApiSettings | None = None,
    user_settings: UserSettings | None = None,
    auth_settings: AuthSettings | None = None,
    sso_settings: SsoSettings | None = None,
    env_store=None,
    ensure_auth: bool = True,
) -> AppServices:
    if (
        api_settings is None
        or user_settings is None
        or auth_settings is None
        or sso_settings is None
    ):
        _api, _user, _auth, _sso = load_settings(env_store=env_store)
        if api_settings is None:
            api_settings = _api
        if user_settings is None:
            user_settings = _user
        if auth_settings is None:
            auth_settings = _auth
        if sso_settings is None:
            sso_settings = _sso

    if ensure_auth:
        auth_manager = AuthManager(api_settings, auth_settings, sso_settings, env_store=env_store)
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
    cashier_bootstrap_service = CashierBootstrapService(
        sso_settings=sso_settings,
        timeout_sec=sso_settings.timeout_sec or 15.0,
        retry_count=api_settings.retry_count,
        retry_interval_sec=api_settings.retry_interval_sec,
    )
    payment_service = PaymentService(
        reservation_api=reservation_api,
        cashier_bootstrap_service=cashier_bootstrap_service,
        cashier_timeout_sec=sso_settings.timeout_sec or 15.0,
        retry_count=api_settings.retry_count,
        retry_interval_sec=api_settings.retry_interval_sec,
    )
    return AppServices(
        workflow=workflow,
        catalog_service=catalog_service,
        payment_service=payment_service,
    )


def parse_cli_args(argv: list[str] | None = None) -> Namespace:
    parser = build_parser()
    args = parser.parse_args() if argv is None else parser.parse_args(list(argv))

    try:
        return validate_and_normalize_args(args)
    except CliValidationError as e:
        raise e


def build_command_context(
    args: Namespace,
    *,
    environ: Mapping[str, str] | None = None,
) -> CommandContext:
    runtime_environ = dict(os.environ if environ is None else environ)
    active_profile = normalize_profile_name(getattr(args, "profile", None), runtime_environ)
    env_store = build_env_store(active_profile, environ=runtime_environ)
    profile_manager = ProfileManager(environ=runtime_environ)
    cmd = get_cmd(args)
    command_kind = get_command_kind(cmd)

    if command_kind == "settings_free" or cmd == "config-doctor":
        auth_manager = AuthManager(ApiSettings(), AuthSettings(), SsoSettings(), env_store=env_store)
        return CommandContext(
            services=AppServices(),
            auth_manager=auth_manager,
            profile_manager=profile_manager,
            env_store=env_store,
            active_profile=active_profile,
            runtime_environ=dict(runtime_environ),
        )

    api_settings, user_settings, auth_settings, sso_settings = load_settings(
        active_profile,
        env_store=env_store,
    )
    merge_cli_overrides(args, api_settings, user_settings)
    auth_manager = AuthManager(api_settings, auth_settings, sso_settings, env_store=env_store)
    services = AppServices()
    if command_kind == "full":
        services = build_app(
            api_settings,
            user_settings,
            auth_settings,
            sso_settings,
            env_store=env_store,
            ensure_auth=True,
        )

    return CommandContext(
        services=services,
        auth_manager=auth_manager,
        profile_manager=profile_manager,
        env_store=env_store,
        active_profile=active_profile,
        runtime_environ=dict(runtime_environ),
    )


def main(argv: list[str] | None = None) -> None:
    setup_logging()

    try:
        args = parse_cli_args(argv)
    except CliValidationError as e:
        logger.error("参数错误: %s", e)
        print(format_request_result("参数检查", False, str(e)))
        return

    cmd = get_cmd(args)
    if requires_trade_no(cmd) and not args.trade_no:
        print("❌ 请指定 --trade-no 订单编号")
        return

    context = build_command_context(args)
    run_command(context, args)


if __name__ == "__main__":
    main()
