from pathlib import Path

import pytest

from src.config.env_store import EnvStore
from argparse import Namespace

from src.config.settings import ApiSettings, UserSettings
from src.main import main, merge_cli_overrides


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

    monkeypatch.setattr("src.main._setup_logging", lambda: None)
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

    monkeypatch.setattr("src.main._setup_logging", lambda: None)
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
