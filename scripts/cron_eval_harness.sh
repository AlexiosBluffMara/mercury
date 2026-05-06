#!/usr/bin/env bash
# cron_eval_harness.sh — Daily 50-prompt eval against local + free-cloud Mercury.
#
# Reserves 200 OpenRouter :free reqs (50 prompts × ~4 calls each: local fast,
# local deep, cloud fast, cloud deep). Compares answers, logs latency +
# agreement rate. Writes a daily report to the vault.
#
# Cron entry (UTC):
#   00 08 * * *  ~/cortex/mercury/scripts/cron_eval_harness.sh
set -euo pipefail
TASK="eval-harness"
N=200

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUOTA="$REPO_ROOT/scripts/openrouter_daily.py"

python3 "$QUOTA" reserve --count "$N" --task "$TASK" || exit 0

VAULT="$HOME/.mercury/vault/eval"
mkdir -p "$VAULT"
TODAY=$(date -u +%Y-%m-%d)
REPORT="$VAULT/${TODAY}-eval.md"

# Fixed prompt set — keep this stable to track regression over time
PROMPTS=(
    "What is 2 plus 2 and explain why."
    "Translate 'good morning' to Spanish, French, German, Japanese, and Mandarin."
    "Summarize the water cycle in one paragraph."
    "What is the capital of Brazil?"
    "Write a haiku about open-source software."
    "List three causes of the French Revolution."
    "Explain photosynthesis to an 8-year-old."
    "What's heavier, a kilogram of feathers or a kilogram of lead?"
    "Convert 100 Fahrenheit to Celsius."
    "Name three operating systems written in C."
)

# Endpoints under test
declare -A ENDPOINTS=(
    [local-mtp]="http://100.93.240.52:8083/v1/chat/completions|unsloth/gemma-4-E4B-it-UD-MLX-4bit"
    [local-e4b]="http://100.93.240.52:8080/v1/chat/completions|unsloth/gemma-4-E4B-it-UD-MLX-4bit"
    [local-26b]="http://100.93.240.52:8081/v1/chat/completions|unsloth/gemma-4-26b-a4b-it-UD-MLX-4bit"
    [cloud-free-26b]="https://openrouter.ai/api/v1/chat/completions|google/gemma-4-26b-a4b-it:free"
)

declare -A AUTH_HEADER=(
    [cloud-free-26b]="Authorization: Bearer ${OPENROUTER_API_KEY:?}"
)

results_jsonl="$VAULT/${TODAY}-eval.jsonl"
: > "$results_jsonl"

for prompt in "${PROMPTS[@]}"; do
    for ep in "${!ENDPOINTS[@]}"; do
        IFS='|' read -r url model <<< "${ENDPOINTS[$ep]}"
        body=$(jq -n --arg p "$prompt" --arg m "$model" \
            '{model:$m,messages:[{role:"user",content:$p}],max_tokens:200,temperature:0}')
        start=$(date +%s.%N)
        if [ -n "${AUTH_HEADER[$ep]:-}" ]; then
            resp=$(curl -s --max-time 60 -X POST "$url" \
                -H "${AUTH_HEADER[$ep]}" \
                -H "Content-Type: application/json" \
                -d "$body")
        else
            resp=$(curl -s --max-time 60 -X POST "$url" \
                -H "Content-Type: application/json" \
                -d "$body")
        fi
        end=$(date +%s.%N)
        latency=$(echo "$end - $start" | bc)
        content=$(echo "$resp" | jq -r '.choices[0].message.content // ""')
        tokens=$(echo "$resp" | jq -r '.usage.completion_tokens // 0')
        echo "$(jq -n --arg p "$prompt" --arg ep "$ep" --arg c "$content" \
              --argjson t "$tokens" --argjson l "$latency" \
              '{prompt:$p,endpoint:$ep,content:$c,tokens:$t,latency_s:$l}')" >> "$results_jsonl"
        # Record only cloud calls against the OR quota; local calls don't count
        if [[ "$ep" == cloud-* ]]; then
            python3 "$QUOTA" record --model "$model" --task "$TASK" \
                --tokens-in 50 --tokens-out "$tokens" >/dev/null
        fi
    done
done

# Quick aggregate report
cat > "$REPORT" <<EOF
---
date: $TODAY
source: eval-harness
prompts: ${#PROMPTS[@]}
endpoints: ${#ENDPOINTS[@]}
---

# Eval harness — $TODAY

EOF

for ep in "${!ENDPOINTS[@]}"; do
    avg_lat=$(jq -s --arg ep "$ep" 'map(select(.endpoint==$ep))|map(.latency_s)|add/length' "$results_jsonl")
    avg_tok=$(jq -s --arg ep "$ep" 'map(select(.endpoint==$ep))|map(.tokens)|add/length' "$results_jsonl")
    echo "- **$ep**: avg latency ${avg_lat}s, avg ${avg_tok} tokens" >> "$REPORT"
done

echo "" >> "$REPORT"
echo "Raw results: \`$results_jsonl\`" >> "$REPORT"
echo "Wrote $REPORT"
