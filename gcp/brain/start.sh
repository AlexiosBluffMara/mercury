#!/usr/bin/env bash
# Mercury Brain entrypoint — runs Ollama on :11434 and the FastAPI facade on
# :$PORT (default 8080). Cloud Run only exposes $PORT publicly.
set -euo pipefail

PORT="${PORT:-8080}"
BRAIN_MODEL="${BRAIN_MODEL:-gemma4:e4b}"

echo "[brain] starting ollama on 127.0.0.1:11434 (model=${BRAIN_MODEL})"
OLLAMA_HOST=127.0.0.1:11434 ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to answer /api/tags before we expose the facade.
for i in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo "[brain] ollama ready after ${i}s"
        break
    fi
    sleep 1
done

# Warm the model into VRAM so the first /v1 request doesn't pay the ~3 s
# load cost. Best-effort — if it fails we still come up.
echo "[brain] warming ${BRAIN_MODEL}"
curl -fsS -X POST http://127.0.0.1:11434/api/generate \
    -H 'content-type: application/json' \
    -d "{\"model\":\"${BRAIN_MODEL}\",\"prompt\":\"hi\",\"stream\":false,\"keep_alive\":\"24h\"}" \
    >/dev/null 2>&1 || echo "[brain] warm-up skipped"

trap 'kill -TERM "${OLLAMA_PID}" 2>/dev/null || true' TERM INT

echo "[brain] starting facade on 0.0.0.0:${PORT}"
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers 1 \
    --no-access-log
