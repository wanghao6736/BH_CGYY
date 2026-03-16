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
    environ: dict[str, str] = {}
    store = EnvStore(path=env_path, environ=environ)
    store.set_values(
        {
            "CGYY_COOKIE": "new-cookie",
            "CGYY_CG_AUTH": "new-auth",
        }
    )
    content = env_path.read_text(encoding="utf-8")
    assert "CGYY_COOKIE=new-cookie" in content
    assert "CGYY_CG_AUTH=new-auth" in content
    assert environ["CGYY_COOKIE"] == "new-cookie"
    assert environ["CGYY_CG_AUTH"] == "new-auth"
