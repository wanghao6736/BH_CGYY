from __future__ import annotations

import logging
from pathlib import Path

from src.api.captcha_api import CaptchaApi
from src.api.catalog_api import CatalogApi
from src.api.client import ApiClient
from src.api.reservation_api import ReservationApi
from src.cli.commands import run as run_command
from src.cli.parser import build_parser
from src.cli.validators import CliValidationError, validate_and_normalize_args
from src.config.settings import load_settings
from src.core.captcha_service import CaptchaService
from src.core.catalog_service import CatalogService
from src.core.reservation_service import ReservationService
from src.core.workflow import ReservationWorkflow
from src.presenters.format import format_request_result
from src.utils.crypto_utils import AesCbcEncryptor
from src.utils.sign_utils import SignBuilder


def _setup_logging() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt)
    root = logging.getLogger()
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(exist_ok=True)
    fh = logging.FileHandler(log_dir / "cgyy.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(fh)


_setup_logging()
logger = logging.getLogger(__name__)


def build_app() -> tuple[ReservationWorkflow, CatalogService]:
    api_settings, user_settings, auth_settings = load_settings()
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


def build_workflow() -> ReservationWorkflow:
    """Backward compatible helper used by test_steps."""
    workflow, _ = build_app()
    return workflow


def _cmd(args) -> str:
    return getattr(args, "cmd", None) or "reserve"


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # 先进行参数规范化与校验，失败则直接返回
    try:
        args = validate_and_normalize_args(args)
    except CliValidationError as e:
        logger.error("参数错误: %s", e)
        print(format_request_result("参数检查", False, str(e)))
        return

    workflow, catalog_service = build_app()

    # 本次调用级别的设置覆盖：优先级为 CLI > main 中的设定值 > .env/环境变量 > 默认值
    if args.date:
        workflow.api_settings.default_search_date = args.date
        workflow.user_settings.reservation_date = args.date
        workflow.user_settings.week_start_date = args.date
    # -s 不指定时保留空字符串，workflow 视为“返回所有开始时间”的方案
    if args.start_time:
        workflow.user_settings.reservation_start_time = args.start_time
    elif _cmd(args) in ("info", "reserve"):
        workflow.user_settings.reservation_start_time = ""
    # -n 不指定时 info/reserve 默认为 1 个时段
    if args.duration is not None:
        workflow.user_settings.reservation_duration_hours = args.duration
    elif _cmd(args) in ("info", "reserve"):
        workflow.user_settings.reservation_duration_hours = 1
    if args.venue_site_id is not None and args.venue_site_id != -1:
        workflow.api_settings.venue_site_id = args.venue_site_id
    if args.buddies:
        workflow.user_settings.buddy_ids = args.buddies

    if _cmd(args) in ("order-detail", "cancel-order") and not args.trade_no:
        print("❌ 请指定 --trade-no 订单编号")
        return

    run_command(workflow, catalog_service, args)


if __name__ == "__main__":
    main()
