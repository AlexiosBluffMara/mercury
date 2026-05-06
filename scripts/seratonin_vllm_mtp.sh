#!/usr/bin/env bash
# seratonin_vllm_mtp.sh — Start vLLM with MTP speculative decoding on Seratonin's RTX 5090.
#
# Runs in WSL2 Ubuntu. Serves google/gemma-4-E4B-it (the official BF16 ~15 GB target)
# accelerated by google/gemma-4-E4B-it-assistant (the official 0.5B drafter, ~100 MB).
# Speculative decoding via --speculative-model + --num-speculative-tokens 5.
#
# Why E4B and not 31B: the official google/gemma-4-31B-it is BF16 only (~58 GB) and
# does not fit in the 5090's 32 GB VRAM. There are no Google-or-Unsloth quants of 31B
# that vLLM accepts (Unsloth ships GGUF/MLX, Google ships only BF16). E4B BF16 fits
# comfortably (target ~15 GB + drafter ~0.1 GB + KV cache + activations ~6 GB =
# ~21 GB used, 11 GB headroom).
#
# Once running, hit it from Windows-side Mercury via http://localhost:8083/v1.
# WSL2 forwards localhost ports to Windows so this works without extra tunneling.
#
# Usage:  ~/mtp-serve/seratonin_vllm_mtp.sh    (call from inside WSL2)
set -euo pipefail

cd ~/mtp-serve
source .venv/bin/activate

# Logs in ~/mtp-serve/logs/
mkdir -p logs

# Local file paths (downloaded via aria2c). Falls back to HF cache if local not present.
TARGET_LOCAL="$HOME/mtp-serve/weights/google-e4b"
DRAFTER_HF="google/gemma-4-E4B-it-assistant"

# Auto-pick: prefer local downloaded weights, fall back to HF cache
if [ -d "$TARGET_LOCAL" ] && ls "$TARGET_LOCAL"/*.safetensors >/dev/null 2>&1; then
    TARGET="$TARGET_LOCAL"
else
    TARGET="google/gemma-4-E4B-it"
fi

echo "Starting vLLM MTP server..."
echo "  target:  $TARGET"
echo "  drafter: $DRAFTER_HF"
echo "  port:    8083"

exec python -m vllm.entrypoints.openai.api_server \
    --model "$TARGET" \
    --speculative-model "$DRAFTER_HF" \
    --num-speculative-tokens 5 \
    --use-v2-block-manager \
    --host 0.0.0.0 \
    --port 8083 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 8192 \
    --dtype bfloat16 \
    2>&1 | tee logs/vllm-mtp.log
