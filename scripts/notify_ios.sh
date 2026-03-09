#!/usr/bin/env bash
set -euo pipefail

# iOS notification via Bark push service.
# Requires env vars: CGYY_BARK_URL, CGYY_BARK_KEY.
# Silently exits when either is unset.
#
# Usage:
#   scripts/notify_ios.sh "Title" "Message"
#   echo "Message" | scripts/notify_ios.sh "Title"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$repo_root/.env" ]]; then
  set -a
  source "$repo_root/.env"
  set +a
fi

bark_url="${CGYY_BARK_URL:-}"
bark_key="${CGYY_BARK_KEY:-}"

if [[ -z "$bark_url" || -z "$bark_key" ]]; then
  exit 0
fi

title="${1:-CGYY}"
shift || true

msg="${*:-}"
if [[ -z "${msg}" ]]; then
  if ! msg="$(cat)"; then
    msg=""
  fi
fi

msg="${msg//$'\r'/}"
msg="${msg:0:500}"

_json_str() {
  local s="${1//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  printf '%s' "$s"
}

payload=$(printf '{
  "body": "%s",
  "title": "%s",
  "badge": 1,
  "sound": "birdsong",
  "icon": "https://www.buaa.edu.cn/images/foot-bicon2.png",
  "group": "CGYY",
  "url": "https://cgyy.buaa.edu.cn/venue/orders"
}' "$(_json_str "$msg")" "$(_json_str "$title")")

curl -sf -X POST "${bark_url%/}/${bark_key}" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d "$payload" \
  >/dev/null 2>&1 || echo "notify_ios: push failed (non-fatal)" >&2

exit 0
