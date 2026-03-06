#!/usr/bin/env bash
set -euo pipefail

# Run reservation workflow once, trying multiple candidate start-times/durations.
#
# Options:
#   -d DATE        预约日期 (YYYY-MM-DD)，透传给 python -m src.main -a reserve -d
#   -p PATTERN     候选时间段列表，如 "15:00/2,17:00/2,19:00/1"
#   -v SITE_ID     覆盖 CGYY_VENUE_SITE_ID
#   -b BUDDIES     覆盖 CGYY_BUDDY_IDS，逗号分隔
#   其他参数将原样透传给 python -m src.main。
#
# Candidate time configuration (highest priority first):
#   1) -p PATTERN                  # explicit pairs HH:MM/DURATION,...
#   2) CGYY_RESERVE_OPTIONS        # same format as -p
#   3) CGYY_RESERVE_START_TIMES / CGYY_RESERVE_DURATIONS
#   4) 若以上均未设置，则不覆盖 CGYY_RESERVATION_*，由 Python 根据 .env 自己决定
#
# Exit code:
#   0 if any attempt prints "✅ [成功] 提交订单"
#   1 otherwise

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

date_arg=""
pattern_arg=""
venue_override=""
buddy_override=""
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
    -v)
      venue_override="$2"
      shift 2
      ;;
    -b)
      buddy_override="$2"
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

if [[ -n "$venue_override" ]]; then
  export CGYY_VENUE_SITE_ID="$venue_override"
fi
if [[ -n "$buddy_override" ]]; then
  export CGYY_BUDDY_IDS="$buddy_override"
fi

python_cmd=("$python_bin" -m src.main -a reserve "${pass_args[@]}")

_run_attempt() {
  local start_time="$1"
  local duration="$2"

  echo "==> Try start=${start_time} duration=${duration}"

  # Override per-attempt; project .env loader will NOT override existing env vars.
  local out
  set +e
  out="$(
    CGYY_RESERVATION_START_TIME="$start_time" \
    CGYY_RESERVATION_DURATION_HOURS="$duration" \
      "${python_cmd[@]}" 2>&1
  )"
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

pairs_source=""
if [[ -n "$pattern_arg" ]]; then
  pairs_source="$pattern_arg"
elif [[ -n "${CGYY_RESERVE_OPTIONS:-}" ]]; then
  pairs_source="${CGYY_RESERVE_OPTIONS}"
fi

if [[ -n "$pairs_source" ]]; then
  IFS=',' read -r -a pairs <<<"$pairs_source"
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

start_times_csv="${CGYY_RESERVE_START_TIMES:-}"
durations_csv="${CGYY_RESERVE_DURATIONS:-}"

if [[ -z "$start_times_csv" && -z "$durations_csv" ]]; then
  # No shell-level pattern configuration: delegate start/duration entirely to Python/.env.
  if _run_attempt "${CGYY_RESERVATION_START_TIME:-}" "${CGYY_RESERVATION_DURATION_HOURS:-}"; then
    exit 0
  fi
  exit 1
fi

start_times=()
durations=()
_split_csv "$start_times_csv" start_times
_split_csv "$durations_csv" durations

if [[ ${#start_times[@]} -eq 0 ]]; then
  start_times=("${CGYY_RESERVATION_START_TIME:-}")
fi
if [[ ${#durations[@]} -eq 0 ]]; then
  durations=("${CGYY_RESERVATION_DURATION_HOURS:-}")
fi

for st in "${start_times[@]}"; do
  for du in "${durations[@]}"; do
    if _run_attempt "$st" "$du"; then
      exit 0
    fi
  done
done

exit 1
