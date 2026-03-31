from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

import requests

from src.config.profiles import build_env_store
from src.logging_setup import setup_logging
from src.parsers.order import SubmitParsed
from src.presenters.format import format_submit_result

logger = logging.getLogger(__name__)

_DEFAULT_TITLE = "CGYY"
_MAX_MESSAGE_LENGTH = 500
_BARK_GROUP = "CGYY"
_BARK_ICON = "https://www.buaa.edu.cn/images/foot-bicon2.png"


def describe_payment_target(target: str) -> str:
    normalized = (target or "").strip()
    if normalized.startswith("weixin://"):
        return "微信支付跳转"
    return "支付页面"


def _normalize_text(value: str, *, fallback: str = "") -> str:
    text = (value or fallback).replace("\r", "").strip()
    if not text:
        text = fallback
    return text[:_MAX_MESSAGE_LENGTH]


def _load_store(
    profile_name: str | None,
    *,
    root: Path | None = None,
    environ: Mapping[str, str] | None = None,
):
    runtime_environ = dict(environ or os.environ)
    return build_env_store(profile_name, root=root, environ=runtime_environ)


def _send_ios_notification(title: str, message: str, *, store, url: str = "") -> bool:
    bark_url = store.get_str("CGYY_BARK_URL", "").strip()
    bark_key = store.get_str("CGYY_BARK_KEY", "").strip()
    if not bark_url or not bark_key:
        return False
    payload = {
        "title": title,
        "body": message,
        "badge": 1,
        "sound": "birdsong",
        "icon": _BARK_ICON,
        "group": _BARK_GROUP,
    }
    normalized_url = _normalize_text(url)
    if normalized_url:
        payload["url"] = normalized_url
    target = f"{bark_url.rstrip('/')}/{bark_key}"
    try:
        response = requests.post(target, json=payload, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("iOS 通知发送失败: %s", exc)
        return False
    return True


def _send_macos_notification(title: str, message: str) -> bool:
    if sys.platform != "darwin":
        return False
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                (
                    "on run argv\n"
                    "  set theTitle to item 1 of argv\n"
                    "  set theMsg to item 2 of argv\n"
                    "  display notification theMsg with title theTitle\n"
                    "end run"
                ),
                title,
                message,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("macOS 通知发送失败: %s", exc)
        return False
    return True


def send_notification(
    title: str,
    message: str = "",
    *,
    url: str = "",
    profile_name: str | None = None,
    root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    channels: Sequence[str] | None = None,
) -> list[str]:
    normalized_title = _normalize_text(title, fallback=_DEFAULT_TITLE)
    normalized_message = _normalize_text(message)
    enabled_channels = tuple(channels or ("macos", "ios"))
    store = _load_store(profile_name, root=root, environ=environ)
    sent_channels: list[str] = []

    for channel in enabled_channels:
        if channel == "macos" and _send_macos_notification(normalized_title, normalized_message):
            sent_channels.append(channel)
        elif channel == "ios" and _send_ios_notification(
            normalized_title,
            normalized_message,
            store=store,
            url=url,
        ):
            sent_channels.append(channel)

    if sent_channels:
        logger.info(
            "通知已发送 title=%s profile=%s channels=%s",
            normalized_title,
            profile_name or "default",
            ",".join(sent_channels),
        )
    else:
        logger.warning(
            "通知未发送：没有可用通道 title=%s profile=%s channels=%s",
            normalized_title,
            profile_name or "default",
            ",".join(enabled_channels),
        )
    return sent_channels


def build_submit_notification_message(
    *,
    success: bool,
    message: str,
    order_id: int = 0,
    trade_no: str = "",
    reservation_start_date: str = "",
    reservation_end_date: str = "",
    display_name: str = "",
    profile_name: str = "",
) -> str:
    submit_parsed = None
    if success and (order_id or trade_no):
        submit_parsed = SubmitParsed(
            order_id=order_id,
            trade_no=trade_no,
            reservation_start_date=reservation_start_date,
            reservation_end_date=reservation_end_date,
        )
    return format_submit_result(
        success,
        message,
        submit_parsed,
        display_name=display_name,
        profile_name=profile_name,
    )


def build_payment_notification_message(
    *,
    success: bool,
    message: str,
    order_id: int = 0,
    trade_no: str = "",
    reservation_start_date: str = "",
    reservation_end_date: str = "",
    display_name: str = "",
    profile_name: str = "",
    payment_target: str = "",
    payment_message: str = "",
) -> str:
    text = build_submit_notification_message(
        success=success,
        message=message,
        order_id=order_id,
        trade_no=trade_no,
        reservation_start_date=reservation_start_date,
        reservation_end_date=reservation_end_date,
        display_name=display_name,
        profile_name=profile_name,
    )
    if payment_target:
        return f"{text}\n🎯 {describe_payment_target(payment_target)} {payment_target}"
    if payment_message:
        return f"{text}\n💳 支付处理 {payment_message}"
    return text


def _read_message_from_stdin() -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read()
    except OSError:
        return ""


def main(argv: Sequence[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="CGYY 通知发送")
    parser.add_argument("title", nargs="?", default=_DEFAULT_TITLE)
    parser.add_argument("message", nargs="?")
    parser.add_argument("-P", "--profile", dest="profile_name", default=None)
    parser.add_argument(
        "--channel",
        choices=("all", "ios", "macos"),
        default="all",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    message = args.message if args.message is not None else _read_message_from_stdin()
    channels = None if args.channel == "all" else (args.channel,)
    send_notification(
        args.title,
        message,
        profile_name=args.profile_name,
        channels=channels,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
