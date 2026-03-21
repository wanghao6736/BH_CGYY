from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from src.config.env_store import EnvStore

DEFAULT_PROFILE = "default"
PROFILE_DIRNAME = ".env.profiles"
PROFILE_ENV_VAR = "CGYY_PROFILE"
DISPLAY_NAME_ENV_VAR = "CGYY_DISPLAY_NAME"

PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_profile_name(name: str | None, environ: Mapping[str, str] | None = None) -> str:
    source = environ if environ is not None else os.environ
    raw = (name or source.get(PROFILE_ENV_VAR) or DEFAULT_PROFILE).strip()
    if not raw:
        return DEFAULT_PROFILE
    if raw == DEFAULT_PROFILE:
        return raw
    if not PROFILE_NAME_RE.fullmatch(raw):
        raise ValueError(f"非法 profile 名称: {raw}")
    return raw


def default_env_path(root: Path | None = None) -> Path:
    return (root or project_root()) / ".env"


def profile_dir(root: Path | None = None) -> Path:
    return (root or project_root()) / PROFILE_DIRNAME


def profile_path(name: str | None, root: Path | None = None) -> Path:
    profile_name = normalize_profile_name(name)
    if profile_name == DEFAULT_PROFILE:
        return default_env_path(root)
    return profile_dir(root) / f"{profile_name}.env"


def profile_layers(name: str | None, root: Path | None = None) -> list[Path]:
    profile_name = normalize_profile_name(name)
    default_path = default_env_path(root)
    if profile_name == DEFAULT_PROFILE:
        return [default_path]
    return [default_path, profile_path(profile_name, root)]


def build_env_store(
    name: str | None = None,
    *,
    root: Path | None = None,
    environ: dict[str, str] | None = None,
) -> EnvStore:
    runtime_environ = environ if environ is not None else dict(os.environ)
    profile_name = normalize_profile_name(name, runtime_environ)
    return EnvStore(
        path=profile_path(profile_name, root),
        paths=profile_layers(profile_name, root),
        environ=runtime_environ,
    )


@dataclass
class ProfileSummary:
    name: str
    path: Path
    display_name: str
    auth_source: str
    sso_source: str


@dataclass
class ProfileValue:
    key: str
    value: str
    source: str
    sensitive: bool = False


class ProfileManager:
    def __init__(
        self,
        *,
        root: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.root = root or project_root()
        self.environ = dict(environ or os.environ)

    def _store(self, name: str | None) -> EnvStore:
        return build_env_store(name, root=self.root, environ=dict(self.environ))

    def _source_label(self, store: EnvStore, key: str, name: str) -> str:
        source = store.get_value_source(key)
        if source is None:
            return "missing"
        current_path = profile_path(name, self.root)
        if source == current_path:
            return "self"
        if source == default_env_path(self.root):
            return "default"
        return source.name

    def list_profiles(self) -> list[ProfileSummary]:
        names = [DEFAULT_PROFILE]
        directory = profile_dir(self.root)
        if directory.exists():
            for path in sorted(directory.glob("*.env")):
                names.append(path.stem)
        items: list[ProfileSummary] = []
        for name in names:
            store = self._store(name)
            display_name = store.get_str(DISPLAY_NAME_ENV_VAR, "") or name
            auth_source = self._source_label(store, "CGYY_CG_AUTH", name)
            if auth_source == "missing":
                auth_source = self._source_label(store, "CGYY_COOKIE", name)
            sso_source = self._source_label(store, "CGYY_SSO_USERNAME", name)
            items.append(
                ProfileSummary(
                    name=name,
                    path=profile_path(name, self.root),
                    display_name=display_name,
                    auth_source=auth_source,
                    sso_source=sso_source,
                )
            )
        return items

    def show_profile(self, name: str) -> list[ProfileValue]:
        store = self._store(name)
        values = store.get_file_values()
        entries: list[ProfileValue] = []
        for key in sorted(values):
            value = values[key]
            sensitive = key in {"CGYY_COOKIE", "CGYY_CG_AUTH", "CGYY_SSO_PASSWORD"}
            shown = value
            if sensitive and value:
                shown = f"{value[:3]}***{len(value)}"
            entries.append(
                ProfileValue(
                    key=key,
                    value=shown,
                    source=self._source_label(store, key, name),
                    sensitive=sensitive,
                )
            )
        return entries

    def add_profile(self, name: str, updates: Mapping[str, str]) -> Path:
        profile_name = normalize_profile_name(name, self.environ)
        if profile_name == DEFAULT_PROFILE:
            raise ValueError("default profile 已存在，无需 add")
        path = profile_path(profile_name, self.root)
        if path.exists():
            raise ValueError(f"profile '{profile_name}' 已存在")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        if updates:
            self._store(profile_name).set_values(updates)
        return path

    def modify_profile(
        self,
        name: str,
        *,
        updates: Mapping[str, str],
        unset_keys: list[str],
    ) -> Path:
        profile_name = normalize_profile_name(name, self.environ)
        path = profile_path(profile_name, self.root)
        if profile_name != DEFAULT_PROFILE and not path.exists():
            raise ValueError(f"profile '{profile_name}' 不存在")
        store = self._store(profile_name)
        if updates:
            store.set_values(updates)
        if unset_keys:
            store.unset_keys(unset_keys)
        return path

    def remove_profile(self, name: str, *, force: bool) -> None:
        profile_name = normalize_profile_name(name, self.environ)
        if profile_name == DEFAULT_PROFILE:
            raise ValueError("default profile 不允许删除")
        if not force:
            raise ValueError("删除 profile 需要 --force")
        path = profile_path(profile_name, self.root)
        if not path.exists():
            raise ValueError(f"profile '{profile_name}' 不存在")
        path.unlink()
