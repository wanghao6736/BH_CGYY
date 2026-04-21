from __future__ import annotations

import logging

from src.cli.commands import get_cmd
from src.cli.commands import run as run_command
from src.cli.handlers.registry import requires_trade_no
from src.cli.validators import CliValidationError
from src.logging_setup import setup_logging
from src.main import build_command_context, parse_cli_args
from src.presenters.format import format_request_result

logger = logging.getLogger(__name__)

LITE_UNSUPPORTED_COMMANDS = frozenset(
    {
        "reserve",
        "fetch-captcha",
        "verify-captcha",
    }
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
    if cmd in LITE_UNSUPPORTED_COMMANDS:
        print(
            format_request_result(
                "命令不可用",
                False,
                f"`{cmd}` 需要 OCR 依赖，请使用 `cgyy` 完整版或安装 `.[ocr]` 后重新打包。",
            )
        )
        return

    if requires_trade_no(cmd) and not args.trade_no:
        print("❌ 请指定 --trade-no 订单编号")
        return

    context = build_command_context(args)
    run_command(context, args)


if __name__ == "__main__":
    main()
