from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Mapping, MutableMapping

logger = logging.getLogger(__name__)


class EnvStore:
    def __init__(
        self,
        path: Path | None = None,
        environ: MutableMapping[str, str] | None = None,
    ) -> None:
        if path is None:
            path = Path(__file__).resolve().parents[2] / ".env"
        self.path = path
        self.environ = environ if environ is not None else os.environ

    def _read_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return self.path.read_text(encoding="utf-8").splitlines()

    def _load_from_file(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in self._read_lines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                values[key] = value
        return values

    def load_to_environ(self) -> None:
        for key, value in self._load_from_file().items():
            if key not in self.environ:
                self.environ[key] = value

    def _get_raw(self, key: str, default: str = "") -> str:
        self.load_to_environ()
        value = self.environ.get(key)
        if value is None:
            return default
        return str(value)

    def get_str(self, key: str, default: str = "") -> str:
        return self._get_raw(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self._get_raw(key, "")
        if raw == "":
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")

    def get_int(self, key: str, default: int = 0) -> int:
        raw = self._get_raw(key, "")
        if raw == "":
            return default
        try:
            return int(raw)
        except ValueError as e:
            raise ValueError(f"环境变量 {key} 不是合法整数: {raw}") from e

    def get_float(self, key: str, default: float = 0.0) -> float:
        raw = self._get_raw(key, "")
        if raw == "":
            return default
        try:
            return float(raw)
        except ValueError as e:
            raise ValueError(f"环境变量 {key} 不是合法浮点数: {raw}") from e

    def set_values(
        self,
        updates: Mapping[str, str],
        *,
        persist: bool = True,
        update_environ: bool = True,
    ) -> None:
        if update_environ:
            for key, value in updates.items():
                self.environ[key] = value
        if persist:
            self._write_values(dict(updates))

    def _write_values(self, updates: dict[str, str]) -> None:
        lines = self._read_lines()
        if not lines:
            lines = []
        remaining = dict(updates)
        updated_lines: list[str] = []

        for line in lines:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in line:
                updated_lines.append(line)
                continue
            key, _ = line.split("=", 1)
            key = key.strip()
            if key in remaining:
                updated_lines.append(f"{key}={remaining.pop(key)}")
            else:
                updated_lines.append(line)

        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        for key, value in remaining.items():
            updated_lines.append(f"{key}={value}")

        content = "\n".join(updated_lines).rstrip() + "\n"
        self.path.write_text(content, encoding="utf-8")
        logger.info("已更新 .env 鉴权信息 path=%s keys=%s", self.path, ",".join(sorted(updates)))

    def clear_environ_keys(self, keys: list[str]) -> None:
        for key in keys:
            self.environ.pop(key, None)
