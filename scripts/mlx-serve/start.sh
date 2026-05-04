#!/usr/bin/env bash
# Boot script for Big Apple's two MLX VLM servers — one per Gemma 4 model.
# Used by both manual launches and the ai.mercury.mlx-{e4b,26b} launchd plists.
#
# Install path on Big Apple: ~/mlx-serve/start.sh (chmod +x)
# Logs:                      ~/.mlx-serve/logs/{e4b,26b}.{log,err.log}
#
# Usage: start.sh {e4b|26b}
#
# Memory budget on M4 Max 48 GB:
#   E4B (port 8080):  ~7 GB peak with audio + image active
#   26B (port 8081):  ~16 GB peak
#   Both running:     ~23 GB total — fits inside macOS's ~40 GB usable budget
#
# kv-bits 4 + turboquant lets us hold larger contexts at the cost of ~3 % gen
# quality (per mlx-vlm benchmarks). Drop to "uniform" if quality matters more.
set -euo pipefail
MODEL_KEY="${1:-}"
cd ~/mlx-serve
source .venv/bin/activate
case "${MODEL_KEY}" in
  e4b)
    exec python -m mlx_vlm.server \
      --model unsloth/gemma-4-E4B-it-UD-MLX-4bit \
      --host 0.0.0.0 --port 8080 \
      --kv-bits 4 --kv-quant-scheme turboquant
    ;;
  26b)
    exec python -m mlx_vlm.server \
      --model mlx-community/gemma-4-26b-a4b-it-4bit \
      --host 0.0.0.0 --port 8081 \
      --kv-bits 4 --kv-quant-scheme turboquant
    ;;
  *)
    echo "usage: $0 {e4b|26b}" >&2; exit 1;;
esac
