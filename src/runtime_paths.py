from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_ROOT_VAR = "CGYY_ROOT"


def _resolve_path(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


def _compiled_root() -> Path:
    executable = Path(sys.argv[0] or sys.executable)
    resolved = _resolve_path(executable)

    # macOS app bundles place the binary under MyApp.app/Contents/MacOS/.
    for parent in resolved.parents:
        if parent.suffix == ".app":
            return parent.parent

    return resolved.parent


def project_root() -> Path:
    override = os.environ.get(ENV_ROOT_VAR, "").strip()
    if override:
        return _resolve_path(Path(override))

    if "__compiled__" in globals():
        return _compiled_root()

    return Path(__file__).resolve().parents[1]
