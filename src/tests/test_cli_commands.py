from argparse import Namespace
from pathlib import Path

from src.cli.commands import run_profile
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
