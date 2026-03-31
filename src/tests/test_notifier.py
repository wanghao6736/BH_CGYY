from __future__ import annotations

import logging
from pathlib import Path

from src.notifier import (build_payment_notification_message,
                          build_submit_notification_message,
                          describe_payment_target, main, send_notification)


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def test_send_notification_uses_profile_bark_settings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    default_env = tmp_path / ".env"
    default_env.write_text("", encoding="utf-8")
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True, exist_ok=True)
    profile_env.write_text(
        "CGYY_BARK_URL=https://api.day.app/\n"
        "CGYY_BARK_KEY=test-key\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, dict[str, object], int]] = []

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _FakeResponse:
        calls.append((url, json, timeout))
        return _FakeResponse()

    monkeypatch.setattr("src.notifier.requests.post", fake_post)

    sent = send_notification(
        "CGYY 预约成功",
        "订单 D1",
        url="weixin://wap/pay?prepayid=123",
        profile_name="alice",
        root=tmp_path,
        environ={},
        channels=("ios",),
    )

    assert sent == ["ios"]
    assert calls == [
        (
            "https://api.day.app/test-key",
            {
                "title": "CGYY 预约成功",
                "body": "订单 D1",
                "badge": 1,
                "sound": "birdsong",
                "icon": "https://www.buaa.edu.cn/images/foot-bicon2.png",
                "group": "CGYY",
                "url": "weixin://wap/pay?prepayid=123",
            },
            5,
        )
    ]


def test_notifier_main_reads_message_from_stdin(monkeypatch) -> None:
    calls = []
    setup_called = []

    def fake_send_notification(title: str, message: str, **kwargs) -> list[str]:
        calls.append((title, message, kwargs))
        return ["ios"]

    monkeypatch.setattr("src.notifier.setup_logging", lambda: setup_called.append(True))
    monkeypatch.setattr("src.notifier._read_message_from_stdin", lambda: "stdin message")
    monkeypatch.setattr("src.notifier.send_notification", fake_send_notification)

    assert main(["--channel", "ios", "CGYY 预约成功"]) == 0
    assert setup_called == [True]
    assert calls == [
        (
            "CGYY 预约成功",
            "stdin message",
            {"profile_name": None, "channels": ("ios",)},
        )
    ]


def test_send_notification_logs_when_no_channel_available(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    default_env = tmp_path / ".env"
    default_env.write_text("", encoding="utf-8")
    monkeypatch.setattr("src.notifier._send_macos_notification", lambda *args, **kwargs: False)
    monkeypatch.setattr("src.notifier._send_ios_notification", lambda *args, **kwargs: False)

    with caplog.at_level(logging.WARNING):
        sent = send_notification(
            "CGYY 预约成功",
            "订单 D1",
            profile_name="default",
            root=tmp_path,
            environ={},
        )

    assert sent == []
    assert "通知未发送：没有可用通道" in caplog.text


def test_build_submit_notification_message_matches_cli_style() -> None:
    text = build_submit_notification_message(
        success=True,
        message="OK",
        order_id=100,
        trade_no="D100",
        reservation_start_date="2026-04-01 18:00",
        reservation_end_date="2026-04-01 19:00",
        display_name="Alice",
        profile_name="alice",
    )

    assert "✅ [成功] 提交订单：OK" in text
    assert "📌 订单ID 100 | 编号 D100" in text
    assert "🕐 预约时间 2026-04-01 18:00 ~ 2026-04-01 19:00" in text
    assert "👤 预定人 Alice | profile alice" in text


def test_build_payment_notification_message_appends_payment_target() -> None:
    text = build_payment_notification_message(
        success=True,
        message="OK",
        order_id=100,
        trade_no="D100",
        reservation_start_date="2026-04-01 18:00",
        reservation_end_date="2026-04-01 19:00",
        display_name="Alice",
        profile_name="alice",
        payment_target="weixin://wap/pay?prepayid=123",
    )

    assert "✅ [成功] 提交订单：OK" in text
    assert "🎯 微信支付跳转 weixin://wap/pay?prepayid=123" in text


def test_describe_payment_target_distinguishes_scheme_and_url() -> None:
    assert describe_payment_target("weixin://wap/pay?prepayid=123") == "微信支付跳转"
    assert describe_payment_target("https://cashier.cc-pay.cn/cashier?id=abc123") == "支付页面"
