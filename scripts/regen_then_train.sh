#!/usr/bin/env bash
# regen_then_train.sh — orchestrator for the Cortex retraining chain.
#
# Step 1: Wait for cortex_train_v2.jsonl to reach the target row count.
# Step 2: Validate the dataset (drop duplicates / templated outputs).
# Step 3: Kick off Unsloth training on the 5090.
# Step 4: Convert to GGUF and load into Ollama as cortex-gemma-4-e4b:v2.
#
# Run after `python -m scripts.generate_neuro_dataset` is launched in
# background (or call it directly — it polls the JSONL until it's big enough).
#
# Usage:
#   bash D:/mercury/scripts/regen_then_train.sh
#   bash D:/mercury/scripts/regen_then_train.sh --target-rows 1500   # accept partial
set -euo pipefail

DATA="D:/cortex/data/cortex_train_v2.jsonl"
PY_CORTEX="C:/Users/soumi/cortex/.venv/Scripts/python.exe"
PY_UNSLOTH="D:/unsloth/studio/.venv/Scripts/python.exe"
TARGET_ROWS=2000
POLL_S=120
LOG="D:/cortex/logs/regen_then_train.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-rows) TARGET_ROWS="$2"; shift 2 ;;
    --poll-s) POLL_S="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$(dirname "${LOG}")"
exec > >(tee -a "${LOG}") 2>&1

echo "=== regen_then_train $(date -Iseconds) ==="
echo "data:        ${DATA}"
echo "target_rows: ${TARGET_ROWS}"

# --- 1. wait for regen to finish (or hit target) ---
while :; do
  if [[ ! -f "${DATA}" ]]; then
    echo "[wait] no file yet"
  else
    rows=$(wc -l < "${DATA}" | tr -d ' ')
    echo "[wait] rows=${rows}/${TARGET_ROWS}"
    if [[ ${rows} -ge ${TARGET_ROWS} ]]; then
      echo "[ok] target reached"
      break
    fi
  fi
  sleep "${POLL_S}"
done

# --- 2. dedupe / quality filter ---
echo
echo "=== validate_dataset.py ==="
"${PY_CORTEX}" -m scripts.validate_dataset \
  --input "${DATA}" \
  --output "${DATA%.jsonl}.clean.jsonl" 2>&1 | tail -20 || {
    echo "[warn] validator missing or failed; proceeding with raw data"
    cp "${DATA}" "${DATA%.jsonl}.clean.jsonl"
}
TRAIN_DATA="${DATA%.jsonl}.clean.jsonl"
echo "train data: ${TRAIN_DATA}"

# --- 3. Unsloth training ---
echo
echo "=== Unsloth training (5090) ==="
if [[ ! -f "${PY_UNSLOTH}" ]]; then
  echo "FATAL: unsloth venv not found at ${PY_UNSLOTH}" >&2
  echo "       create it with:  uv venv D:/unsloth/studio/.venv && uv pip install unsloth ..." >&2
  exit 3
fi

# Make sure TRIBE is NOT loaded — Unsloth needs ~16GB and can't coexist.
free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' ')
echo "[gpu] free=${free} MiB"
if [[ ${free} -lt 18000 ]]; then
  echo "[gpu] freeing VRAM — unloading any Ollama models"
  curl -s -X POST http://localhost:11434/api/generate -d '{"model":"gemma4:31b","keep_alive":"0s"}' >/dev/null || true
  curl -s -X POST http://localhost:11434/api/generate -d '{"model":"gemma4:e4b","keep_alive":"0s"}' >/dev/null || true
  curl -s -X POST http://localhost:11434/api/generate -d '{"model":"cortex-gemma-4-e4b","keep_alive":"0s"}' >/dev/null || true
  sleep 8
fi

cd D:/cortex
"${PY_UNSLOTH}" scripts/train_cortex.py \
  --dataset "${TRAIN_DATA}" \
  --output-dir outputs/cortex-v2 \
  --epochs 3 2>&1

# --- 4. GGUF + Ollama register ---
echo
echo "=== GGUF + Ollama ==="
GGUF_DIR="D:/cortex/outputs/cortex-v2-gguf"
if [[ -d "${GGUF_DIR}" ]] && [[ -f "${GGUF_DIR}/Modelfile" ]]; then
  ollama create cortex-gemma-4-e4b:v2 -f "${GGUF_DIR}/Modelfile" 2>&1
  ollama list | grep cortex
else
  echo "[warn] GGUF not produced at ${GGUF_DIR} — review Unsloth log"
fi

echo
echo "=== DONE  $(date -Iseconds) ==="
