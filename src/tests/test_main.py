from argparse import Namespace
from pathlib import Path

import pytest

from src.cli.commands import run as run_command
from src.cli.handlers.registry import get_command_kind
from src.config.env_store import EnvStore
from src.config.settings import ApiSettings, UserSettings
from src.main import (build_command_context, main, merge_cli_overrides,
                      parse_cli_args)


def test_merge_cli_overrides_ignores_missing_business_args_for_profile_command() -> None:
    api_settings = ApiSettings()
    user_settings = UserSettings()

    merge_cli_overrides(
        Namespace(cmd="profile", profile_cmd="list"),
        api_settings,
        user_settings,
    )

    assert api_settings.venue_site_id == ApiSettings.venue_site_id
    assert user_settings.profile_name == UserSettings.profile_name


def test_main_logout_clears_encrypted_auth_without_cred_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    seeded_store = EnvStore(path=env_path, paths=[env_path], environ={"CGYY_CRED_KEY": "unit-test-key"})
    seeded_store.set_values(
        {
            "CGYY_COOKIE": "cookie-token",
            "CGYY_CG_AUTH": "auth-token",
        }
    )
    logout_store = EnvStore(path=env_path, paths=[env_path], environ={})

    class Parser:
        def parse_args(self) -> Namespace:
            return Namespace(cmd="logout", profile="default")

    monkeypatch.setattr("src.main.setup_logging", lambda: None)
    monkeypatch.setattr("src.main.build_parser", lambda: Parser())
    monkeypatch.setattr("src.main.validate_and_normalize_args", lambda args: args)
    monkeypatch.setattr("src.main.build_env_store", lambda *args, **kwargs: logout_store)
    monkeypatch.setattr("src.main.ProfileManager", lambda *args, **kwargs: object())

    main()

    content = env_path.read_text(encoding="utf-8")
    assert "CGYY_COOKIE=\n" in content
    assert "CGYY_CG_AUTH=\n" in content
    assert "enc:v1:" not in content


def test_main_profile_modify_skips_settings_load_for_encrypted_default_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    profile_env.write_text("", encoding="utf-8")
    seeded_store = EnvStore(
        path=default_env,
        paths=[default_env],
        environ={"CGYY_CRED_KEY": "unit-test-key"},
    )
    seeded_store.set_values({"CGYY_SSO_PASSWORD": "secret-password"})
    runtime_store = EnvStore(path=default_env, paths=[default_env], environ={})

    class Parser:
        def parse_args(self) -> Namespace:
            return Namespace(
                cmd="profile",
                profile_cmd="modify",
                profile=None,
                name="alice",
                set_values=["CGYY_DISPLAY_NAME=Alice"],
                unset_keys=[],
                force=False,
            )

    monkeypatch.setattr("src.main.setup_logging", lambda: None)
    monkeypatch.setattr("src.main.build_parser", lambda: Parser())
    monkeypatch.setattr("src.main.validate_and_normalize_args", lambda args: args)
    monkeypatch.setattr("src.main.build_env_store", lambda *args, **kwargs: runtime_store)
    monkeypatch.setattr(
        "src.main.ProfileManager",
        lambda *args, **kwargs: __import__("src.config.profiles", fromlist=["ProfileManager"]).ProfileManager(
            root=tmp_path,
            environ={},
        ),
    )

    main()

    assert "CGYY_DISPLAY_NAME=Alice\n" in profile_env.read_text(encoding="utf-8")


def test_get_command_kind_splits_execution_paths() -> None:
    assert get_command_kind("logout") == "settings_free"
    assert get_command_kind("profile") == "settings_free"
    assert get_command_kind("login") == "settings_only"
    assert get_command_kind("auth-status") == "settings_only"
    assert get_command_kind("config-doctor") == "settings_only"
    assert get_command_kind("pay") == "full"
    assert get_command_kind("reserve") == "full"


def test_parse_cli_args_uses_real_parser_and_validator() -> None:
    args = parse_cli_args(
        [
            "reserve",
            "-P",
            "default",
            "-d",
            "2026/3/30",
            "-s",
            "9.5",
            "-n",
            "2",
        ]
    )

    assert args.cmd == "reserve"
    assert args.profile == "default"
    assert args.date == "2026-03-30"
    assert args.start_time == "09:30"
    assert args.duration == 2


def test_parse_cli_args_normalizes_pay_options() -> None:
    args = parse_cli_args(
        [
            "pay",
            "-P",
            "Default",
            "-t",
            "D260331000575",
            "--mode",
            "mobile",
            "--pay-way-name",
            " wxpay_wap ",
        ]
    )

    assert args.cmd == "pay"
    assert args.profile == "Default"
    assert args.trade_no == "D260331000575"
    assert args.mode == "mobile"
    assert args.pay_way_name == "wxpay_wap"


def test_build_app_includes_payment_service() -> None:
    from src.config.settings import AuthSettings, SsoSettings

    services = __import__("src.main", fromlist=["build_app"]).build_app(
        api_settings=ApiSettings(
            base_url="https://cgyy.example.invalid",
            prefix="prefix",
            app_key="app-key",
            aes_cbc_key="0123456789abcdef",
            aes_cbc_iv="0123456789abcdef",
            retry_count=2,
            retry_interval_sec=0.1,
        ),
        user_settings=UserSettings(),
        auth_settings=AuthSettings(cookie="cookie=1", cg_authorization="auth-1"),
        sso_settings=SsoSettings(timeout_sec=9.0),
        ensure_auth=False,
    )

    assert services.workflow is not None
    assert services.catalog_service is not None
    assert services.payment_service is not None


def test_main_logout_does_not_load_settings_or_build_services(monkeypatch: pytest.MonkeyPatch) -> None:
    class Parser:
        def parse_args(self) -> Namespace:
            return Namespace(cmd="logout", profile="default")

    monkeypatch.setattr("src.main.setup_logging", lambda: None)
    monkeypatch.setattr("src.main.build_parser", lambda: Parser())
    monkeypatch.setattr("src.main.validate_and_normalize_args", lambda args: args)
    monkeypatch.setattr("src.main.build_env_store", lambda *args, **kwargs: object())
    monkeypatch.setattr("src.main.ProfileManager", lambda *args, **kwargs: object())
    monkeypatch.setattr("src.main.load_settings", lambda *args, **kwargs: (_ for _ in ()
                                                                           ).throw(AssertionError("load_settings should not run")))
    monkeypatch.setattr("src.main.build_app", lambda *args, **kwargs: (_ for _ in ()
                                                                       ).throw(AssertionError("build_app should not run")))
    monkeypatch.setattr("src.main.AuthManager", lambda *args, **kwargs: object())
    monkeypatch.setattr("src.main.run_command", lambda context, args: None)

    main()


def test_build_command_context_for_login_skips_service_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = Namespace(cmd="login", profile="default")

    monkeypatch.setattr("src.main.load_settings", lambda *args, **
                        kwargs: (ApiSettings(), UserSettings(), object(), object()))
    monkeypatch.setattr("src.main.AuthManager", lambda *args, **kwargs: "auth-manager")
    monkeypatch.setattr("src.main.ProfileManager", lambda *args, **kwargs: "profile-manager")
    monkeypatch.setattr("src.main.build_app", lambda *args, **kwargs: (_ for _ in ()
                                                                       ).throw(AssertionError("build_app should not run")))
    monkeypatch.setattr("src.main.build_env_store", lambda *args, **kwargs: "env-store")

    context = build_command_context(args, environ={})

    assert context.auth_manager == "auth-manager"
    assert context.profile_manager == "profile-manager"
    assert context.services.workflow is None
    assert context.services.catalog_service is None


def test_build_command_context_respects_explicit_empty_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = Namespace(cmd="logout", profile=None)

    monkeypatch.setenv("CGYY_PROFILE", "alice")
    monkeypatch.setattr("src.main.build_env_store", lambda *args, **kwargs: "env-store")
    monkeypatch.setattr("src.main.ProfileManager", lambda *args, **kwargs: "profile-manager")
    monkeypatch.setattr("src.main.AuthManager", lambda *args, **kwargs: "auth-manager")

    context = build_command_context(args, environ={})

    assert context.active_profile == "default"
    assert context.runtime_environ == {}


def test_build_command_context_for_config_doctor_skips_service_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = Namespace(cmd="config-doctor", profile="default", probe=False)

    monkeypatch.setattr("src.main.load_settings", lambda *args, **kwargs: (_ for _ in ()
                                                                           ).throw(AssertionError("load_settings should not run")))
    monkeypatch.setattr("src.main.AuthManager", lambda *args, **kwargs: "auth-manager")
    monkeypatch.setattr("src.main.ProfileManager", lambda *args, **kwargs: "profile-manager")
    monkeypatch.setattr("src.main.build_app", lambda *args, **kwargs: (_ for _ in ()
                                                                       ).throw(AssertionError("build_app should not run")))
    monkeypatch.setattr("src.main.build_env_store", lambda *args, **kwargs: "env-store")

    context = build_command_context(args, environ={})

    assert context.auth_manager == "auth-manager"
    assert context.profile_manager == "profile-manager"
    assert context.services.workflow is None
    assert context.services.catalog_service is None


def test_main_smoke_uses_real_parser_and_dispatches_profile_list(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = []

    monkeypatch.setattr("src.main.setup_logging", lambda: None)
    monkeypatch.setattr("src.main.AuthManager", lambda *args, **kwargs: "auth-manager")
    monkeypatch.setattr("src.main.ProfileManager", lambda *args, **kwargs: "profile-manager")
    monkeypatch.setattr("src.main.build_env_store", lambda *args, **kwargs: "env-store")
    monkeypatch.setattr(
        "src.main.run_command",
        lambda context, args: captured.append((context, args)),
    )

    main(["profile", "list"])

    assert len(captured) == 1
    context, args = captured[0]
    assert args.cmd == "profile"
    assert args.profile_cmd == "list"
    assert context.active_profile == "default"
    assert context.auth_manager == "auth-manager"
    assert context.profile_manager == "profile-manager"


def test_run_command_dispatches_via_registry_defaulting_to_reserve(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = []

    monkeypatch.setattr(
        "src.cli.commands.get_handler",
        lambda cmd: (lambda context, args: captured.append((cmd, context, args))),
    )

    context = object()
    args = Namespace(cmd=None)

    run_command(context, args)

    assert len(captured) == 1
    assert captured[0][0] == "reserve"


def test_main_config_doctor_smoke_uses_real_parser_and_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default_env = tmp_path / ".env"
    default_env.write_text(
        "\n".join(
            [
                "CGYY_BASE_URL=https://example.invalid",
                "CGYY_PREFIX=prefix",
                "CGYY_APP_KEY=app-key",
                "CGYY_AES_CBC_KEY=0123456789abcdef",
                "CGYY_AES_CBC_IV=0123456789abcdef",
                "CGYY_PHONE=13800138000",
                "CGYY_VENUE_SITE_ID=57",
                "CGYY_RESERVATION_SLOT_COUNT=2",
                "CGYY_SELECTION_STRATEGY=same_first_digit",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.main.setup_logging", lambda: None)
    monkeypatch.setattr(
        "src.main.build_env_store",
        lambda name, environ=None: __import__("src.config.profiles", fromlist=["build_env_store"]).build_env_store(
            name,
            root=tmp_path,
            environ=environ,
        ),
    )
    monkeypatch.setattr(
        "src.main.ProfileManager",
        lambda *args, **kwargs: __import__("src.config.profiles", fromlist=["ProfileManager"]).ProfileManager(
            root=tmp_path,
            environ=kwargs.get("environ") or {},
        ),
    )

    main(["config-doctor"])

    out = capsys.readouterr().out
    assert "[成功] 配置诊断" in out
    assert "CGYY_BASE_URL: https://example.invalid" in out


def test_main_config_doctor_reports_bad_settings_instead_of_crashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default_env = tmp_path / ".env"
    default_env.write_text("CGYY_VENUE_SITE_ID=abc\n", encoding="utf-8")

    monkeypatch.setattr("src.main.setup_logging", lambda: None)
    monkeypatch.setattr(
        "src.main.build_env_store",
        lambda name, environ=None: __import__("src.config.profiles", fromlist=["build_env_store"]).build_env_store(
            name,
            root=tmp_path,
            environ=environ,
        ),
    )
    monkeypatch.setattr(
        "src.main.ProfileManager",
        lambda *args, **kwargs: __import__("src.config.profiles", fromlist=["ProfileManager"]).ProfileManager(
            root=tmp_path,
            environ=kwargs.get("environ") or {},
        ),
    )

    main(["config-doctor"])

    out = capsys.readouterr().out
    assert "[失败] 配置诊断" in out
    assert "CGYY_VENUE_SITE_ID" in out
