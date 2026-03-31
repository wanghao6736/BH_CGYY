from pathlib import Path

from src.api.endpoints import CgyyEndpoints, SsoEndpoints
from src.auth.manager import AuthManager
from src.auth.models import ServiceAuthState
from src.config.env_store import ENC_PREFIX
from src.config.profiles import (MANAGED_CRED_KEY_FILENAME, ProfileManager,
                                 build_env_store, ensure_managed_cred_key,
                                 managed_cred_key_path)
from src.config.settings import (ApiSettings, AuthSettings, SsoSettings,
                                 UserSettings, load_settings)


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


def test_profile_manager_creates_managed_cred_key_for_sensitive_updates(tmp_path: Path) -> None:
    manager = ProfileManager(root=tmp_path, environ={})

    manager.add_profile(
        "alice",
        {
            "CGYY_SSO_PASSWORD": "secret-password",
        },
    )

    key_path = managed_cred_key_path(tmp_path)
    assert key_path.exists()
    assert key_path.read_text(encoding="utf-8").strip()


def test_profile_manager_inspection_works_without_cred_key(tmp_path: Path) -> None:
    writer = ProfileManager(root=tmp_path, environ={"CGYY_CRED_KEY": "unit-test-key"})
    writer.add_profile(
        "alice",
        {
            "CGYY_DISPLAY_NAME": "Alice",
            "CGYY_COOKIE": "cookie-token",
            "CGYY_SSO_PASSWORD": "secret-password",
        },
    )

    reader = ProfileManager(root=tmp_path, environ={})

    summaries = {item.name: item for item in reader.list_profiles()}
    values = {item.key: item for item in reader.show_profile("alice")}

    assert summaries["alice"].display_name == "Alice"
    assert summaries["alice"].auth_source == "self"
    assert values["CGYY_COOKIE"].sensitive is True
    assert values["CGYY_COOKIE"].value.startswith(ENC_PREFIX)
    assert values["CGYY_SSO_PASSWORD"].sensitive is True
    assert values["CGYY_SSO_PASSWORD"].value.startswith(ENC_PREFIX)


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


def test_auth_manager_creates_managed_cred_key_when_persisting_auth(tmp_path: Path) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text("", encoding="utf-8")
    profile_env.write_text("", encoding="utf-8")

    env_store = build_env_store(
        "alice",
        root=tmp_path,
        environ={},
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

    key_path = managed_cred_key_path(tmp_path)
    assert key_path.exists()
    assert key_path.read_text(encoding="utf-8").strip()
    assert "CGYY_COOKIE=enc:v1:" in profile_env.read_text(encoding="utf-8")


def test_build_env_store_loads_managed_cred_key_from_disk(tmp_path: Path) -> None:
    default_env = tmp_path / ".env"
    seeded_store = build_env_store(
        None,
        root=tmp_path,
        environ={"CGYY_CRED_KEY": "unit-test-key"},
    )
    seeded_store.set_values({"CGYY_COOKIE": "cookie-token"})
    default_env.write_text(default_env.read_text(encoding="utf-8"), encoding="utf-8")
    managed_cred_key_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    managed_cred_key_path(tmp_path).write_text("unit-test-key\n", encoding="utf-8")

    store = build_env_store(None, root=tmp_path, environ={})

    assert store.get_str("CGYY_COOKIE", "") == "cookie-token"
    assert store.environ["CGYY_CRED_KEY"] == "unit-test-key"


def test_ensure_managed_cred_key_creates_new_filename(tmp_path: Path) -> None:
    environ: dict[str, str] = {}

    key = ensure_managed_cred_key(environ, root=tmp_path)

    assert key
    assert environ["CGYY_CRED_KEY"] == key
    assert (tmp_path / ".env.profiles" / MANAGED_CRED_KEY_FILENAME).exists()


def test_load_settings_uses_code_defaults_for_sso_urls(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("CGYY_SSO_ENABLED=1\n", encoding="utf-8")

    _, _, _, sso_settings = load_settings(
        env_store=build_env_store(None, root=tmp_path, environ={}),
    )

    assert sso_settings.login_base_url == f"{SsoEndpoints.DOMAIN}{SsoEndpoints.LOGIN_ENTRY}"
    assert sso_settings.service_url == f"{CgyyEndpoints.BASE_URL}{CgyyEndpoints.SSO_LOGIN}"


def test_load_settings_ignores_low_frequency_runtime_tuning_envs(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "CGYY_RETRY_COUNT=9",
                "CGYY_RETRY_INTERVAL_SEC=9.9",
                "CGYY_CAPTCHA_DELAY_MIN=0.1",
                "CGYY_CAPTCHA_DELAY_MAX=0.2",
                "CGYY_ORDER_PIN_X_MIN=1",
                "CGYY_ORDER_PIN_X_MAX=2",
                "CGYY_ORDER_PIN_Y_MIN=3",
                "CGYY_ORDER_PIN_Y_MAX=4",
                "CGYY_SSO_TIMEOUT_SEC=1.5",
                "CGYY_SSO_MAX_REDIRECTS=1",
                "CGYY_AUTH_PERSIST_TO_ENV=0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    api_settings, user_settings, _, sso_settings = load_settings(
        env_store=build_env_store(None, root=tmp_path, environ={}),
    )

    assert api_settings.retry_count == ApiSettings.retry_count
    assert api_settings.retry_interval_sec == ApiSettings.retry_interval_sec
    assert api_settings.captcha_delay_min == ApiSettings.captcha_delay_min
    assert api_settings.captcha_delay_max == ApiSettings.captcha_delay_max
    assert user_settings.order_pin_x_min == UserSettings.order_pin_x_min
    assert user_settings.order_pin_x_max == UserSettings.order_pin_x_max
    assert user_settings.order_pin_y_min == UserSettings.order_pin_y_min
    assert user_settings.order_pin_y_max == UserSettings.order_pin_y_max
    assert sso_settings.timeout_sec == SsoSettings.timeout_sec
    assert sso_settings.max_redirects == SsoSettings.max_redirects
    assert sso_settings.persist_to_env is SsoSettings.persist_to_env
