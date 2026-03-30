#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/notify_macos.sh "Title" "Message"
#   echo "Message" | scripts/notify_macos.sh "Title"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python_bin="${CGYY_PYTHON_BIN:-}"
if [[ -z "$python_bin" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python_bin="python3"
  else
    python_bin="python"
  fi
fi

title="${1:-CGYY}"
shift || true

msg="${*:-}"
if [[ -z "${msg}" ]]; then
  if ! msg="$(cat)"; then
    msg=""
  fi
fi

exec "$python_bin" -m src.notifier --channel macos "$title" "$msg"
