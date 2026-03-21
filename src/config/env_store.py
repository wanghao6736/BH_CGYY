from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Mapping, MutableMapping

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

logger = logging.getLogger(__name__)

ENC_PREFIX = "enc:v1:"
SENSITIVE_ENV_KEYS = frozenset(
    {
        "CGYY_COOKIE",
        "CGYY_CG_AUTH",
        "CGYY_SSO_PASSWORD",
    }
)


class EnvStore:
    def __init__(
        self,
        path: Path | None = None,
        paths: list[Path] | None = None,
        environ: MutableMapping[str, str] | None = None,
    ) -> None:
        if path is None:
            path = Path(__file__).resolve().parents[2] / ".env"
        self.path = path
        self.paths = list(paths) if paths is not None else [path]
        self.environ = environ if environ is not None else dict(os.environ)

    def _read_lines(self, path: Path | None = None) -> list[str]:
        read_path = path or self.path
        if not read_path.exists():
            return []
        return read_path.read_text(encoding="utf-8").splitlines()

    def _decode_value(self, key: str, value: str) -> str:
        if not value.startswith(ENC_PREFIX):
            return value
        raw_key = self.environ.get("CGYY_CRED_KEY", "")
        if not raw_key:
            raise ValueError(f"环境变量 {key} 已加密，但未提供 CGYY_CRED_KEY")
        payload = value[len(ENC_PREFIX):]
        try:
            blob = base64.urlsafe_b64decode(payload.encode("utf-8"))
        except Exception as e:
            raise ValueError(f"环境变量 {key} 的密文格式非法") from e
        nonce = blob[:12]
        tag = blob[12:28]
        ciphertext = blob[28:]
        digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        cipher = AES.new(digest, AES.MODE_GCM, nonce=nonce)
        try:
            plain = cipher.decrypt_and_verify(ciphertext, tag)
        except Exception as e:
            raise ValueError(f"环境变量 {key} 解密失败") from e
        return plain.decode("utf-8")

    def _encode_value(self, key: str, value: str) -> str:
        if key not in SENSITIVE_ENV_KEYS or value == "":
            return value
        raw_key = self.environ.get("CGYY_CRED_KEY", "")
        if not raw_key:
            raise ValueError(f"写入 {key} 需要提供 CGYY_CRED_KEY")
        digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        nonce = get_random_bytes(12)
        cipher = AES.new(digest, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(value.encode("utf-8"))
        payload = base64.urlsafe_b64encode(nonce + tag + ciphertext).decode("utf-8")
        return f"{ENC_PREFIX}{payload}"

    def _load_from_file(self, path: Path | None = None) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in self._read_lines(path):
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                values[key] = self._decode_value(key, value)
        return values

    def _load_from_files(self) -> tuple[dict[str, str], dict[str, Path]]:
        values: dict[str, str] = {}
        sources: dict[str, Path] = {}
        for path in self.paths:
            loaded = self._load_from_file(path)
            for key, value in loaded.items():
                values[key] = value
                sources[key] = path
        return values, sources

    def load_to_environ(self) -> None:
        values, _ = self._load_from_files()
        for key, value in values.items():
            if key not in self.environ:
                self.environ[key] = value

    def _get_raw(self, key: str, default: str = "") -> str:
        value = self.environ.get(key)
        if value is None:
            values, _ = self._load_from_files()
            if key not in values:
                return default
            value = values[key]
            self.environ[key] = value
        return self._decode_value(key, str(value))

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
            stored_updates = {
                key: self._encode_value(key, value)
                for key, value in updates.items()
            }
            self._write_values(stored_updates)

    def _write_values(self, updates: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
        logger.info("已更新配置文件 path=%s keys=%s", self.path, ",".join(sorted(updates)))

    def unset_keys(
        self,
        keys: list[str],
        *,
        persist: bool = True,
        update_environ: bool = True,
    ) -> None:
        if update_environ:
            self.clear_environ_keys(keys)
        if not persist:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = self._read_lines()
        updated_lines: list[str] = []
        removed = set(keys)
        for line in lines:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in line:
                updated_lines.append(line)
                continue
            key, _ = line.split("=", 1)
            if key.strip() in removed:
                continue
            updated_lines.append(line)
        content = "\n".join(updated_lines).rstrip()
        if content:
            content += "\n"
        self.path.write_text(content, encoding="utf-8")

    def get_file_values(self) -> dict[str, str]:
        values, _ = self._load_from_files()
        return values

    def get_value_source(self, key: str) -> Path | None:
        _, sources = self._load_from_files()
        return sources.get(key)

    def clear_environ_keys(self, keys: list[str]) -> None:
        for key in keys:
            self.environ.pop(key, None)
