#!/usr/bin/env bash
# post_scan_resume_regen.sh — wait for the live brain scan to finish, then
# kick off the cortex training-data regen + Unsloth retrain chain.
#
# Why a watcher: the scan needs TRIBE v2 (~22 GB), the regen needs gemma4:31b
# (~21 GB). They cannot share the 5090. So we serialize: scan first (high
# user value, fast), then the long-running regen+train (overnight).
set -euo pipefail

SCAN_ID="${1:-79119a20c833}"
PY="C:/Users/soumi/cortex/.venv/Scripts/python.exe"
LOG="D:/cortex/logs/post_scan_chain.log"
mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

echo "=== post_scan watcher $(date -Iseconds) ==="
echo "watching scan: $SCAN_ID"

while :; do
  st=$(curl -s "http://127.0.0.1:8765/api/scan/$SCAN_ID" \
        | "$PY" -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null)
  gpu=$(curl -s "http://127.0.0.1:8765/api/health" \
        | "$PY" -c "import sys,json; print(json.load(sys.stdin)['gpu']['state'])" 2>/dev/null)
  echo "[$(date +%H:%M:%S)] scan=$st  gpu=$gpu"
  case "$st" in
    completed|failed|error) break ;;
  esac
  sleep 30
done

echo
echo "=== scan settled (status=$st). Saving result snapshot ==="
mkdir -p D:/mercury/kimi_proof/08_live_scan_demo
curl -s "http://127.0.0.1:8765/api/scan/$SCAN_ID" > "D:/mercury/kimi_proof/08_live_scan_demo/scan_${SCAN_ID}.json"
ls -la "D:/mercury/kimi_proof/08_live_scan_demo/"

echo
echo "=== free VRAM for gemma4:31b regen ==="
# scheduler should swap back to gemma after scan; force-evict TRIBE just in case
curl -s -X POST http://localhost:11434/api/generate \
  -d '{"model":"gemma4:e4b","keep_alive":"0s","prompt":""}' >/dev/null
sleep 4
nvidia-smi --query-gpu=memory.free,memory.used --format=csv,noheader

echo
echo "=== resume regen (will take ~2 hr) ==="
cd D:/cortex && nohup "$PY" -m scripts.generate_neuro_dataset \
  --backend ollama:gemma4:31b --n-per-family 20 \
  --output data/cortex_train_v2.jsonl \
  --resume --supervised \
  --log-file data/regen_v2.jsonl \
  > D:/cortex/logs/regen_v2_stdout.log 2>&1 &
REGEN=$!
echo "REGEN_PID=$REGEN"

echo
echo "=== orchestrator (auto-trigger Unsloth retrain at 2000 rows) ==="
nohup bash D:/mercury/scripts/regen_then_train.sh > D:/cortex/logs/orchestrator.log 2>&1 &
ORCH=$!
echo "ORCH_PID=$ORCH"

echo
echo "All chains launched. Tail with:"
echo "  tail -f D:/cortex/logs/regen_v2_stdout.log"
echo "  tail -f D:/cortex/logs/orchestrator.log"
