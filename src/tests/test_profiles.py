from pathlib import Path

from src.auth.manager import AuthManager
from src.auth.models import ServiceAuthState
from src.config.profiles import ProfileManager, build_env_store
from src.config.settings import ApiSettings, AuthSettings, SsoSettings, load_settings


def test_load_settings_merges_default_and_profile_values(tmp_path: Path) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text(
        "\n".join(
            [
                "CGYY_PHONE=13800138000",
                "CGYY_BUDDY_IDS=1,2,3",
                "CGYY_DISPLAY_NAME=Default User",
                "",
            ]
        ),
        encoding="utf-8",
    )
    profile_env.write_text(
        "\n".join(
            [
                "CGYY_DISPLAY_NAME=Alice",
                "CGYY_PHONE=13900000000",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _, user_settings, _, _ = load_settings(
        "alice",
        env_store=build_env_store("alice", root=tmp_path, environ={}),
    )

    assert user_settings.profile_name == "alice"
    assert user_settings.display_name == "Alice"
    assert user_settings.phone == "13900000000"
    assert user_settings.buddy_ids == "1,2,3"


def test_profile_manager_unset_restores_default_inheritance(tmp_path: Path) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text("CGYY_BUDDY_IDS=1,2,3\n", encoding="utf-8")
    profile_env.write_text("CGYY_BUDDY_IDS=7,8\n", encoding="utf-8")
    manager = ProfileManager(root=tmp_path, environ={})

    manager.modify_profile("alice", updates={}, unset_keys=["CGYY_BUDDY_IDS"])
    _, user_settings, _, _ = load_settings(
        "alice",
        env_store=build_env_store("alice", root=tmp_path, environ={}),
    )

    assert "CGYY_BUDDY_IDS" not in profile_env.read_text(encoding="utf-8")
    assert user_settings.buddy_ids == "1,2,3"


def test_profile_manager_show_masks_sensitive_values(tmp_path: Path) -> None:
    manager = ProfileManager(root=tmp_path, environ={"CGYY_CRED_KEY": "unit-test-key"})

    manager.add_profile(
        "alice",
        {
            "CGYY_DISPLAY_NAME": "Alice",
            "CGYY_SSO_PASSWORD": "secret-password",
        },
    )

    values = {item.key: item for item in manager.show_profile("alice")}

    assert values["CGYY_SSO_PASSWORD"].sensitive is True
    assert values["CGYY_SSO_PASSWORD"].value != "secret-password"
    assert values["CGYY_SSO_PASSWORD"].source == "self"


def test_auth_manager_persists_auth_to_active_profile(tmp_path: Path) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text("", encoding="utf-8")
    profile_env.write_text("", encoding="utf-8")

    env_store = build_env_store(
        "alice",
        root=tmp_path,
        environ={"CGYY_CRED_KEY": "unit-test-key"},
    )
    manager = AuthManager(
        ApiSettings(),
        AuthSettings(),
        SsoSettings(),
        env_store=env_store,
    )

    manager._persist_auth(  # type: ignore[attr-defined]
        ServiceAuthState(
            service_name="cgyy",
            cookie="cookie-token",
            cg_authorization="auth-token",
        )
    )

    assert "CGYY_COOKIE=enc:v1:" in profile_env.read_text(encoding="utf-8")
    assert default_env.read_text(encoding="utf-8") == ""
