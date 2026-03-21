from pathlib import Path

from src.config.env_store import EnvStore


def test_env_store_reads_typed_values_and_updates_environ(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "CGYY_RETRY_COUNT=5",
                "CGYY_SSO_ENABLED=1",
                "CGYY_SSO_TIMEOUT_SEC=3.5",
                "CGYY_PHONE=13800138000",
                "",
            ]
        ),
        encoding="utf-8",
    )
    environ: dict[str, str] = {}
    store = EnvStore(path=env_path, environ=environ)
    assert store.get_int("CGYY_RETRY_COUNT", 0) == 5
    assert store.get_bool("CGYY_SSO_ENABLED", False) is True
    assert store.get_float("CGYY_SSO_TIMEOUT_SEC", 0.0) == 3.5
    assert store.get_str("CGYY_PHONE", "") == "13800138000"
    assert environ["CGYY_PHONE"] == "13800138000"


def test_env_store_set_values_updates_file_and_environ(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("CGYY_COOKIE=old\n", encoding="utf-8")
    environ: dict[str, str] = {"CGYY_CRED_KEY": "unit-test-key"}
    store = EnvStore(path=env_path, environ=environ)
    store.set_values(
        {
            "CGYY_COOKIE": "new-cookie",
            "CGYY_CG_AUTH": "new-auth",
        }
    )
    content = env_path.read_text(encoding="utf-8")
    assert "CGYY_COOKIE=enc:v1:" in content
    assert "CGYY_CG_AUTH=enc:v1:" in content
    assert environ["CGYY_COOKIE"] == "new-cookie"
    assert environ["CGYY_CG_AUTH"] == "new-auth"


def test_env_store_reads_layered_values_and_allows_empty_override(tmp_path: Path) -> None:
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
                "CGYY_BUDDY_IDS=",
                "",
            ]
        ),
        encoding="utf-8",
    )

    store = EnvStore(paths=[default_env, profile_env], path=profile_env, environ={})

    assert store.get_str("CGYY_PHONE", "") == "13800138000"
    assert store.get_str("CGYY_DISPLAY_NAME", "") == "Alice"
    assert store.get_str("CGYY_BUDDY_IDS", "fallback") == ""


def test_env_store_encrypts_sensitive_values_when_key_present(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    environ = {"CGYY_CRED_KEY": "unit-test-key"}
    store = EnvStore(path=env_path, environ=environ)

    store.set_values({"CGYY_SSO_PASSWORD": "secret-password"})

    content = env_path.read_text(encoding="utf-8")
    assert "CGYY_SSO_PASSWORD=enc:v1:" in content
    assert "secret-password" not in content
    assert store.get_str("CGYY_SSO_PASSWORD", "") == "secret-password"
