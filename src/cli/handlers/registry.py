from __future__ import annotations

from argparse import Namespace
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from src.cli.context import CommandContext
from src.cli.handlers.auth import (handle_auth_status, handle_login,
                                   handle_logout)
from src.cli.handlers.doctor import handle_config_doctor
from src.cli.handlers.payment import handle_pay
from src.cli.handlers.profile import handle_profile
from src.cli.handlers.query import (handle_cancel_order, handle_catalog,
                                    handle_fetch_captcha, handle_info,
                                    handle_order_detail, handle_verify_captcha)
from src.cli.handlers.reservation import handle_reserve

CommandHandler = Callable[[CommandContext, Namespace], None]
CommandKind = Literal["settings_free", "settings_only", "full"]


@dataclass(frozen=True)
class CommandSpec:
    handler: CommandHandler
    kind: CommandKind = "full"
    requires_trade_no: bool = False


COMMAND_SPECS: dict[str, CommandSpec] = {
    "auth-status": CommandSpec(handle_auth_status, kind="settings_only"),
    "cancel-order": CommandSpec(handle_cancel_order, requires_trade_no=True),
    "catalog": CommandSpec(handle_catalog),
    "config-doctor": CommandSpec(handle_config_doctor, kind="settings_only"),
    "fetch-captcha": CommandSpec(handle_fetch_captcha),
    "info": CommandSpec(handle_info),
    "login": CommandSpec(handle_login, kind="settings_only"),
    "logout": CommandSpec(handle_logout, kind="settings_free"),
    "order-detail": CommandSpec(handle_order_detail, requires_trade_no=True),
    "pay": CommandSpec(handle_pay, requires_trade_no=True),
    "profile": CommandSpec(handle_profile, kind="settings_free"),
    "reserve": CommandSpec(handle_reserve),
    "verify-captcha": CommandSpec(handle_verify_captcha),
}


def get_handler(cmd: str) -> CommandHandler:
    return COMMAND_SPECS.get(cmd, COMMAND_SPECS["reserve"]).handler


def get_command_kind(cmd: str) -> CommandKind:
    return COMMAND_SPECS.get(cmd, COMMAND_SPECS["reserve"]).kind


def get_registered_commands() -> set[str]:
    return set(COMMAND_SPECS)


def requires_trade_no(cmd: str) -> bool:
    return COMMAND_SPECS.get(cmd, COMMAND_SPECS["reserve"]).requires_trade_no
