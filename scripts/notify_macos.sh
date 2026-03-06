#!/usr/bin/env bash
set -euo pipefail

# macOS notification via built-in osascript.
# Usage:
#   scripts/notify_macos.sh "Title" "Message"
#   echo "Message" | scripts/notify_macos.sh "Title"

title="${1:-CGYY}"
shift || true

msg="${*:-}"
if [[ -z "${msg}" ]]; then
  # Read from stdin if message not provided as args
  if ! msg="$(cat)"; then
    msg=""
  fi
fi

# Trim to reduce chance of exceeding notification limits
msg="${msg//$'\r'/}"
msg="${msg:0:500}"

osascript -e 'on run argv
  set theTitle to item 1 of argv
  set theMsg to item 2 of argv
  display notification theMsg with title theTitle
end run' "$title" "$msg"

