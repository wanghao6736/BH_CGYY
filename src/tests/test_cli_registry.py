from __future__ import annotations

from argparse import _SubParsersAction

from src.cli.handlers.registry import (get_command_kind, get_registered_commands,
                                       requires_trade_no)
from src.cli.parser import build_parser


def _parser_commands() -> set[str]:
    parser = build_parser()
    for action in parser._actions:
        if isinstance(action, _SubParsersAction):
            return set(action.choices)
    raise AssertionError("parser missing subcommands")


def test_registered_commands_cover_parser_top_level_commands() -> None:
    assert _parser_commands() <= get_registered_commands()


def test_command_registry_exposes_expected_command_kinds() -> None:
    assert get_command_kind("logout") == "settings_free"
    assert get_command_kind("profile") == "settings_free"
    assert get_command_kind("login") == "settings_only"
    assert get_command_kind("auth-status") == "settings_only"
    assert get_command_kind("config-doctor") == "settings_only"
    assert get_command_kind("reserve") == "full"
    assert get_command_kind("unknown-command") == "full"


def test_command_registry_marks_trade_no_commands() -> None:
    assert requires_trade_no("order-detail") is True
    assert requires_trade_no("cancel-order") is True
    assert requires_trade_no("config-doctor") is False
