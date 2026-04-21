from pathlib import Path

from src import runtime_paths


def test_project_root_prefers_explicit_env_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(runtime_paths.ENV_ROOT_VAR, str(tmp_path))

    assert runtime_paths.project_root() == tmp_path.resolve()


def test_project_root_uses_parent_of_macos_app_bundle_when_compiled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app_binary = tmp_path / "dist" / "CGYY.app" / "Contents" / "MacOS" / "cgyy-ui"
    app_binary.parent.mkdir(parents=True)
    app_binary.write_text("", encoding="utf-8")

    monkeypatch.delenv(runtime_paths.ENV_ROOT_VAR, raising=False)
    monkeypatch.setitem(runtime_paths.__dict__, "__compiled__", True)
    monkeypatch.setattr("sys.argv", [str(app_binary)])

    try:
        assert runtime_paths.project_root() == (tmp_path / "dist").resolve()
    finally:
        runtime_paths.__dict__.pop("__compiled__", None)
