#!/usr/bin/env bash
set -euo pipefail

# Run reservation workflow once, trying multiple candidate start-times/durations.
#
# Options:
#   -d DATE        预约日期 (YYYY-MM-DD)，透传给 python -m src.main reserve -d
#   -p PATTERN     候选时间段列表，如 "15:00/2,17:00/2,19:00/1"
#   -P PROFILE     覆盖本次调用的 profile
#   -v SITE_ID     覆盖 CGYY_VENUE_SITE_ID
#   -b BUDDIES     覆盖 CGYY_BUDDY_IDS，逗号分隔
#   其他参数将原样透传给 python -m src.main。
#
# Candidate time configuration:
#   1) -p PATTERN                  # explicit pairs HH:MM/DURATION,...
#   2) 若未指定 -p，则不覆盖开始时间/时段数，由 Python 根据当前 profile 与默认配置自行决定
#
# Exit code:
#   0 if any attempt prints "✅ [成功] 提交订单"
#   1 otherwise

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

date_arg=""
pattern_arg=""
pass_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d)
      date_arg="$2"
      pass_args+=("-d" "$2")
      shift 2
      ;;
    -p)
      pattern_arg="$2"
      shift 2
      ;;
    -P|--profile)
      pass_args+=("-P" "$2")
      shift 2
      ;;
    -v)
      pass_args+=("-v" "$2")
      shift 2
      ;;
    -b)
      pass_args+=("-b" "$2")
      shift 2
      ;;
    *)
      pass_args+=("$1")
      shift 1
      ;;
  esac
done

python_bin="${CGYY_PYTHON_BIN:-}"
if [[ -z "$python_bin" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python_bin="python3"
  else
    python_bin="python"
  fi
fi

python_cmd=("$python_bin" -m src.main reserve "${pass_args[@]}")

_run_attempt() {
  local start_time="$1"
  local duration="$2"

  echo "==> Try start=${start_time} duration=${duration}"

  local out
  set +e
  local cmd=("${python_cmd[@]}")
  if [[ -n "$start_time" && -n "$duration" ]]; then
    cmd+=("-s" "$start_time" "-n" "$duration")
  fi
  out="$("${cmd[@]}" 2>&1)"
  local rc=$?
  set -e

  echo "$out"

  if echo "$out" | grep -q "✅ \\[成功\\] 提交订单"; then
    return 0
  fi

  # If python command itself failed hard, preserve visibility (still treated as failure)
  if [[ $rc -ne 0 ]]; then
    echo "!! python exited with code ${rc}" >&2
  fi
  return 1
}

_split_csv() {
  local s="${1:-}"
  local arr_name="$2"
  # NOTE: macOS ships bash 3.2 by default; nameref (-n) is not available.
  eval "${arr_name}=()"
  if [[ -z "$s" ]]; then
    return 0
  fi
  local IFS=,
  local parts=()
  read -r -a parts <<<"$s"
  local part trimmed
  for part in "${parts[@]}"; do
    trimmed="${part#"${part%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    [[ -z "$trimmed" ]] && continue
    eval "${arr_name}+=(\"\$trimmed\")"
  done
}

if [[ -n "$pattern_arg" ]]; then
  IFS=',' read -r -a pairs <<<"$pattern_arg"
  for p in "${pairs[@]}"; do
    p="${p//[[:space:]]/}"
    [[ -z "$p" ]] && continue
    if [[ "$p" != */* ]]; then
      echo "Invalid pattern item: '$p' (expected HH:MM/DURATION)" >&2
      continue
    fi
    start="${p%%/*}"
    dur="${p##*/}"
    if _run_attempt "$start" "$dur"; then
      exit 0
    fi
  done
  exit 1
fi
 
# No shell-level pattern configuration: delegate start/duration entirely to Python/profile config.
if _run_attempt "" ""; then
  exit 0
fi
exit 1
