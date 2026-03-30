"""CLI 命令分发与兼容导出。"""
from __future__ import annotations

from argparse import Namespace

from src.cli.context import CommandContext
from src.cli.handlers.auth import run_auth_status, run_login, run_logout
from src.cli.handlers.doctor import run_config_doctor
from src.cli.handlers.profile import run_profile
from src.cli.handlers.query import (run_cancel_order, run_catalog,
                                    run_fetch_captcha, run_info,
                                    run_order_detail, run_verify_captcha)
from src.cli.handlers.registry import get_handler
from src.cli.handlers.reservation import run_reserve


def get_cmd(args: Namespace) -> str:
    """从 argparse 结果中取子命令名，默认 'reserve'。"""
    return getattr(args, "cmd", None) or "reserve"


def run(context: CommandContext, args: Namespace) -> None:
    handler = get_handler(get_cmd(args))
    handler(context, args)


__all__ = [
    "get_cmd",
    "run",
    "run_auth_status",
    "run_cancel_order",
    "run_catalog",
    "run_config_doctor",
    "run_fetch_captcha",
    "run_info",
    "run_login",
    "run_logout",
    "run_order_detail",
    "run_profile",
    "run_reserve",
    "run_verify_captcha",
]
