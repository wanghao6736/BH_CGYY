from argparse import Namespace
from pathlib import Path

from src.cli.commands import run_profile
from src.cli.handlers.shared import get_profile_name_from_env_path
from src.config.profiles import ProfileManager


def test_run_profile_list_prints_known_profiles(tmp_path: Path, capsys) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text("CGYY_DISPLAY_NAME=Default User\n", encoding="utf-8")
    profile_env.write_text("CGYY_DISPLAY_NAME=Alice\n", encoding="utf-8")
    manager = ProfileManager(root=tmp_path, environ={})

    run_profile(
        manager,
        Namespace(profile_cmd="list", name=None, set_values=[], unset_keys=[], force=False),
    )

    out = capsys.readouterr().out
    assert "default" in out
    assert "alice" in out


def test_run_profile_modify_updates_file(tmp_path: Path, capsys) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text("CGYY_BUDDY_IDS=1,2,3\n", encoding="utf-8")
    profile_env.write_text("CGYY_BUDDY_IDS=7,8\n", encoding="utf-8")
    manager = ProfileManager(root=tmp_path, environ={})

    run_profile(
        manager,
        Namespace(
            profile_cmd="modify",
            name="alice",
            set_values=["CGYY_DISPLAY_NAME=Alice"],
            unset_keys=["CGYY_BUDDY_IDS"],
            force=False,
        ),
    )

    out = capsys.readouterr().out
    content = profile_env.read_text(encoding="utf-8")
    assert "CGYY_DISPLAY_NAME=Alice" in content
    assert "CGYY_BUDDY_IDS" not in content
    assert "成功" in out


def test_run_profile_show_warns_about_legacy_sso_fields(tmp_path: Path, capsys) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text("", encoding="utf-8")
    profile_env.write_text("CGYY_SSO_USERNAME=alice\nCGYY_SSO_PASSWORD=secret\n", encoding="utf-8")
    manager = ProfileManager(root=tmp_path, environ={})

    run_profile(
        manager,
        Namespace(profile_cmd="show", name="alice", set_values=[], unset_keys=[], force=False),
    )

    out = capsys.readouterr().out
    assert "CGYY_SSO_USERNAME" in out
    assert "仅供 CLI 自动化模式使用" in out
    assert "cleanup-legacy-sso alice" in out


def test_run_profile_cleanup_legacy_sso_unsets_username_and_password(tmp_path: Path, capsys) -> None:
    default_env = tmp_path / ".env"
    profile_env = tmp_path / ".env.profiles" / "alice.env"
    profile_env.parent.mkdir(parents=True)
    default_env.write_text("", encoding="utf-8")
    profile_env.write_text(
        "CGYY_SSO_USERNAME=alice\nCGYY_SSO_PASSWORD=secret\nCGYY_PHONE=13800138000\n",
        encoding="utf-8")
    manager = ProfileManager(root=tmp_path, environ={})

    run_profile(
        manager,
        Namespace(profile_cmd="cleanup-legacy-sso", name="alice", set_values=[], unset_keys=[], force=False),
    )

    out = capsys.readouterr().out
    content = profile_env.read_text(encoding="utf-8")
    assert "CGYY_SSO_USERNAME" not in content
    assert "CGYY_SSO_PASSWORD" not in content
    assert "CGYY_PHONE=13800138000" in content
    assert "legacy SSO 清理" in out


def test_get_profile_name_from_env_path_strips_env_suffix() -> None:
    assert get_profile_name_from_env_path(".env") == "default"
    assert get_profile_name_from_env_path("alice.env") == "alice"
