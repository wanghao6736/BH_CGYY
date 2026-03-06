#!/usr/bin/env bash
set -euo pipefail

# Poll reservation periodically until success (or max attempts).
#
# Env defaults (can be overridden by CLI flags):
#   CGYY_POLL_INTERVAL_SEC   default 1800 (30 minutes)
#   CGYY_POLL_MAX_ATTEMPTS   default 0 (0 = infinite)
#   CGYY_NOTIFY_ON_FAIL      default 0 (set 1 to notify when giving up)
#
# Candidate time configs are the same as scripts/reserve_once.sh:
#   CGYY_RESERVE_OPTIONS / CGYY_RESERVE_START_TIMES / CGYY_RESERVE_DURATIONS
#
# Usage:
#   scripts/poll_reserve.sh [-d YYYY-MM-DD] [-p HH:MM/N,...] [-v SITE_ID] [-b BUDDIES] [-i INTERVAL_SEC] [-n MAX_ATTEMPTS]

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

interval_override=""
max_attempts_override=""

pass_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -i)
      interval_override="$2"
      shift 2
      ;;
    -n)
      max_attempts_override="$2"
      shift 2
      ;;
    *)
      pass_args+=("$1")
      shift 1
      ;;
  esac
done

interval="${interval_override:-${CGYY_POLL_INTERVAL_SEC:-1800}}"
max_attempts="${max_attempts_override:-${CGYY_POLL_MAX_ATTEMPTS:-0}}"
notify_on_fail="${CGYY_NOTIFY_ON_FAIL:-0}"

notify() {
  local title="$1"
  shift || true
  local msg="${*:-}"
  if [[ -x "$repo_root/scripts/notify_macos.sh" ]]; then
    "$repo_root/scripts/notify_macos.sh" "$title" "$msg" || true
  fi
}

attempt=0
while :; do
  attempt=$((attempt + 1))
  echo "===== Poll attempt #${attempt} ====="

  set +e
  out="$("$repo_root/scripts/reserve_once.sh" "${pass_args[@]}" 2>&1)"
  rc=$?
  set -e

  echo "$out"

  if [[ $rc -eq 0 ]]; then
    summary="$(echo "$out" | grep -E "✅ \\[成功\\] 提交订单|📌 订单ID|🕐 预约时间" | head -n 3 | tr '\n' ' ' || true)"
    [[ -z "$summary" ]] && summary="提交订单成功（详见终端输出）"
    notify "CGYY 预约成功" "$summary"
    exit 0
  fi

  if [[ "$max_attempts" != "0" && "$attempt" -ge "$max_attempts" ]]; then
    echo "Reached max attempts (${max_attempts}). Giving up."
    if [[ "$notify_on_fail" == "1" ]]; then
      notify "CGYY 预约未成功" "已尝试 ${attempt} 次，仍未提交成功。"
    fi
    exit 1
  fi

  echo "Sleep ${interval}s..."
  sleep "$interval"
done

