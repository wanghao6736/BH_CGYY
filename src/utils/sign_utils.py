from dataclasses import dataclass
from hashlib import md5
from typing import Any, Dict, Iterable, List


def params_to_sign_parts(params: Dict[str, Any]) -> List[str]:
    """
    将参数字典按 key 排序后，拼接为 sign 所需的键值对列表。
    规则：key 排序 → 每个 key 与 value 拼接为 "{key}{value}" → 返回列表供后续拼接。
    """
    return [f"{k}{v}" for k, v in sorted(params.items())]


@dataclass
class SignBuilder:
    prefix: str

    def _md5(self, s: str) -> str:
        return md5(s.encode()).hexdigest()

    def build(self, rel_path: str, parts: Iterable[str]) -> str:
        sign_str = f"{self.prefix}{rel_path}" + "".join(parts)
        return self._md5(sign_str)
