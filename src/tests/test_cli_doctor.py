from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from src.auth.manager import AuthManager
from src.auth.models import AuthBootstrapResult, ServiceAuthState
from src.cli.context import AppServices, CommandContext
from src.cli.handlers.doctor import run_config_doctor
from src.config.profiles import ProfileManager, build_env_store
from src.config.settings import load_settings


def _write_profile_files(
    root: Path,
    *,
    buddy_ids: str = "",
    include_auth: bool = True,
    sso_enabled: bool = False,
    sso_username: str = "",
    sso_password: str = "",
    sso_login_url: str = "",
    sso_service_url: str = "",
) -> None:
    default_env = root / ".env"
    profile_env = root / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_lines = [
        "CGYY_BASE_URL=https://example.invalid",
        "CGYY_PREFIX=prefix",
        "CGYY_APP_KEY=app-key",
        "CGYY_AES_CBC_KEY=0123456789abcdef",
        "CGYY_AES_CBC_IV=0123456789abcdef",
        "CGYY_PHONE=13800138000",
        "CGYY_VENUE_SITE_ID=57",
        "CGYY_RESERVATION_SLOT_COUNT=2",
        "CGYY_SELECTION_STRATEGY=same_first_digit,cheapest",
    ]
    if include_auth:
        default_lines.extend(
            [
                "CGYY_COOKIE=cookie-token",
                "CGYY_CG_AUTH=auth-token",
            ]
        )
    if sso_enabled:
        default_lines.append("CGYY_SSO_ENABLED=1")
    if sso_login_url:
        default_lines.append(f"CGYY_SSO_LOGIN_URL={sso_login_url}")
    if sso_service_url:
        default_lines.append(f"CGYY_SSO_SERVICE_URL={sso_service_url}")
    if sso_username:
        default_lines.append(f"CGYY_SSO_USERNAME={sso_username}")
    if sso_password:
        default_lines.append(f"CGYY_SSO_PASSWORD={sso_password}")
    default_env.write_text("\n".join(default_lines) + "\n", encoding="utf-8")
    profile_lines = [
        "CGYY_DISPLAY_NAME=Alice",
    ]
    if buddy_ids:
        profile_lines.append(f"CGYY_BUDDY_IDS={buddy_ids}")
    profile_env.write_text("\n".join(profile_lines) + "\n", encoding="utf-8")


def _build_context(root: Path) -> CommandContext:
    env_store = build_env_store("alice", root=root, environ={})
    api_settings, user_settings, auth_settings, sso_settings = load_settings(
        "alice",
        env_store=env_store,
    )
    return CommandContext(
        services=AppServices(),
        auth_manager=AuthManager(api_settings, auth_settings, sso_settings, env_store=env_store),
        profile_manager=ProfileManager(root=root, environ={}),
        env_store=env_store,
        active_profile="alice",
        runtime_environ={},
    )


def test_run_config_doctor_reports_effective_sources_and_optional_warnings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_profile_files(tmp_path)
    context = _build_context(tmp_path)

    run_config_doctor(context, Namespace(probe=False))

    out = capsys.readouterr().out
    assert "profile=alice" in out
    assert "CGYY_BASE_URL: https://example.invalid | 来源 default" in out
    assert "CGYY_DISPLAY_NAME: Alice | 来源 self" in out
    assert "CGYY_BUDDY_IDS: (未配置)" in out
    assert "存在提醒项 CGYY_BUDDY_IDS" in out


def test_run_config_doctor_reports_probe_warning(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_profile_files(
        tmp_path,
        buddy_ids="1,2",
        sso_enabled=True,
        sso_login_url="https://login.example.invalid",
        sso_service_url="https://service.example.invalid",
        sso_username="alice",
        sso_password="secret",
    )
    context = _build_context(tmp_path)

    monkeypatch.setattr(
        "src.cli.handlers.doctor._auth_probe_result",
        lambda *args, **kwargs: AuthBootstrapResult(
            reused=False,
            refreshed=False,
            state=ServiceAuthState(service_name="cgyy", source="env"),
        ),
    )

    run_config_doctor(context, Namespace(probe=True))

    out = capsys.readouterr().out
    assert "AUTH_PROBE: 失败 | 来源 env | 实时探活" in out
    assert "存在提醒项 AUTH_PROBE" in out


def test_run_config_doctor_fails_when_auth_and_sso_fallback_are_unusable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_profile_files(tmp_path, include_auth=False, sso_enabled=False)
    context = _build_context(tmp_path)

    run_config_doctor(context, Namespace(probe=False))

    out = capsys.readouterr().out
    assert "[失败] 诊断结论" in out
    assert "缺少可用鉴权：未配置 CGYY_COOKIE/CGYY_CG_AUTH，且未启用 SSO 自动登录" in out
    assert "当前可运行" not in out


def test_run_config_doctor_surfaces_missing_sso_credentials_in_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_profile_files(
        tmp_path,
        include_auth=True,
        sso_enabled=True,
        sso_login_url="https://login.example.invalid",
        sso_service_url="https://service.example.invalid",
    )
    context = _build_context(tmp_path)

    run_config_doctor(context, Namespace(probe=False))

    out = capsys.readouterr().out
    assert "SSO 回退配置缺少 CGYY_SSO_USERNAME, CGYY_SSO_PASSWORD" in out
    assert "配置完整，可继续查询/预约" not in out
