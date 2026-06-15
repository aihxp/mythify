#!/usr/bin/env sh
set -eu

cursor="${MYTHIFY_CHAT_CURSOR:-chat}"
mythify_bin="${MYTHIFY_BIN:-mythify}"

if [ "${MYTHIFY_CHAT_HOOK_MARK:-0}" = "1" ]; then
  exec "$mythify_bin" report --cursor "$cursor" --mark
fi

output=$("$mythify_bin" report --since last --cursor "$cursor" --format chat 2>/dev/null || true)

case "$output" in
  *"0 new events"*)
    exit 0
    ;;
  "")
    exit 0
    ;;
esac

printf '%s\n' "$output"
