#!/usr/bin/env bash
# cron_log_digest.sh — Daily one-page memo from yesterday's Mercury logs.
#
# Reserves 50 OpenRouter :free reqs from the daily 1000 budget, runs 24h of
# logs through gemma-4-26b-a4b-it:free, writes the memo to the Obsidian vault.
#
# Cron entry (UTC):
#   05 06 * * *  ~/cortex/mercury/scripts/cron_log_digest.sh
set -euo pipefail
TASK="log-digest"
N=50

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUOTA="$REPO_ROOT/scripts/openrouter_daily.py"

# Reserve budget; bail if exhausted
python3 "$QUOTA" reserve --count "$N" --task "$TASK" || exit 0

LOG_DIR="$HOME/.mercury/logs"
VAULT="$HOME/.mercury/vault/daily"
mkdir -p "$VAULT"

YESTERDAY=$(date -u -d 'yesterday' +%Y-%m-%d 2>/dev/null || date -u -v-1d +%Y-%m-%d)
TODAY=$(date -u +%Y-%m-%d)
OUT="$VAULT/${TODAY}-log-digest.md"

# Concatenate yesterday's logs (last ~50 KB to fit in context)
LOG_BLOB=$(find "$LOG_DIR" -newermt "$YESTERDAY" ! -newermt "$TODAY" -name '*.log' -print0 2>/dev/null \
    | xargs -0 cat 2>/dev/null \
    | tail -c 50000)

if [ -z "$LOG_BLOB" ]; then
    echo "No logs from $YESTERDAY — skipping" >&2
    exit 0
fi

PROMPT=$(cat <<EOF
You are reviewing one day of Mercury Agent logs from $YESTERDAY. Write a one-page
markdown memo with these sections:

  ## Active sessions
  ## Errors and warnings (count + 1-line summary each)
  ## Skills invoked (count + which)
  ## Notable user requests (5-10 bullets, redacted)
  ## What I would investigate tomorrow

Logs follow:
$LOG_BLOB
EOF
)

# Hit OpenRouter free tier directly with curl (no Mercury dependency in cron)
RESP=$(curl -s --max-time 90 -X POST https://openrouter.ai/api/v1/chat/completions \
    -H "Authorization: Bearer ${OPENROUTER_API_KEY:?OPENROUTER_API_KEY not set}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg p "$PROMPT" '{"model":"google/gemma-4-26b-a4b-it:free","messages":[{"role":"user","content":$p}],"max_tokens":1500}')")

CONTENT=$(echo "$RESP" | jq -r '.choices[0].message.content // empty')

if [ -z "$CONTENT" ]; then
    echo "No content from OpenRouter, response: $RESP" >&2
    exit 1
fi

cat > "$OUT" <<EOF
---
date: $TODAY
source: log-digest
generator: gemma-4-26b-a4b-it:free
---

# Daily log digest — $TODAY (covering $YESTERDAY)

$CONTENT
EOF

# Record the spend (1 free call)
python3 "$QUOTA" record --model "google/gemma-4-26b-a4b-it:free" --task "$TASK" --tokens-in 0 --tokens-out 0

echo "Wrote $OUT"
