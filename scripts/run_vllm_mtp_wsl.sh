#!/usr/bin/env bash
# run_vllm_mtp_wsl.sh — start vLLM 0.20+ with MTP speculative decoding for Gemma 4 E4B.
# Run inside WSL2: bash /mnt/d/mercury/scripts/run_vllm_mtp_wsl.sh
set -euo pipefail
cd ~/mtp-serve
mkdir -p logs

# Kill any stale instance
pkill -f 'vllm.entrypoints.openai.api_server' 2>/dev/null || true
sleep 1

# vLLM 0.20+ uses --speculative-config (JSON string) instead of separate flags
SPEC_JSON='{"model":"google/gemma-4-E4B-it-assistant","num_speculative_tokens":5,"method":"draft_model"}'

exec .venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$HOME/mtp-serve/weights/google-e4b" \
    --speculative-config "$SPEC_JSON" \
    --host 0.0.0.0 --port 8083 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 8192 \
    --dtype bfloat16
