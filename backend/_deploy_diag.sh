#!/usr/bin/env bash
# TEMPORARY build-diagnostic helper. Uploads a build log to the bot's own
# Telegram "short description" so build failures can be read back when
# Render's API does not expose build logs. Delete after use.
LOG="${1:-/tmp/b.log}"
: "${BOT_TOKEN:?BOT_TOKEN not set}"
TAIL="$(tail -c 900 "$LOG" 2>/dev/null | tr '\n\r\t' '   ' | tr -d '"')"
curl -s -m 30 -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setMyDescription" \
  --data-urlencode "description=${TAIL}" \
  --data "language_code=en" > /dev/null
echo "[diag] log tail uploaded"
