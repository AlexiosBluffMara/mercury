# Hermes / Mercury — local-only wiring (texting status)

## Right now (verified live)

| Thing | State |
|---|---|
| Mercury config model | `moonshotai/kimi-k2.6` via `nous-portal` |
| Nous Portal auth | logged in, **but credits = 0 → 401 on every call** |
| API-key fallbacks (OpenAI / Anthropic / OpenRouter / Z.AI / Kimi-direct) | all unset |
| Local model alternative | `cortex-gemma-4-e4b:latest` + `gemma4:e4b` already in Ollama |
| Discord / WhatsApp gateway | **not running** (no listener on 8765) |
| GPU | `gemma4:31b` loaded — training-data regen in progress, ~3hr ETA |

**Bottom line:** if you text the Discord bot or WhatsApp number right now,
nothing replies. Two unrelated things have to be true: (a) the gateway has
to be up, (b) the model has to actually generate.

## What unblocks "I can text Hermes" (pick one)

### Path A — top up Nous (fastest, 0-touch on this box)
1. Add credits at https://portal.nousresearch.com
2. Verify: `curl -s https://inference-api.nousresearch.com/v1/models -H "Authorization: Bearer $NOUS_API_KEY" | head -c 200`
3. Start the gateway: `mercury gateway up discord` (Discord-only is the lightest)

### Path B — switch to local Ollama, no credits needed
**Wait for the regen to finish first** (or pause it — see below). Otherwise
you'll evict `gemma4:31b` from VRAM and break the regen run.

```sh
# 1. Switch Hermes default model
mercury model
# pick: ollama → cortex-gemma-4-e4b:latest   (or gemma4:e4b for vanilla)

# 2. Start the Discord gateway
mercury gateway up discord

# 3. Verify
curl -s http://localhost:8765/status
```

### Path C — pause regen, use local now, resume regen later
The generator was launched with `--supervised --resume`, so it can be
killed and restarted without losing progress.

```sh
# 1. Stop the regen (graceful)
ps -ef | grep generate_neuro_dataset | grep -v grep
# kill the python PID (NOT the bash wrapper)
kill <PID>

# 2. Free Ollama VRAM so the small model can load
curl -s -X POST http://localhost:11434/api/generate \
  -d '{"model":"gemma4:31b","keep_alive":"0s"}'

# 3. Switch + start gateway (Path B)

# 4. Later, resume the regen — it'll skip what's already done
cd D:/cortex && nohup "C:/Users/soumi/cortex/.venv/Scripts/python.exe" \
  -m scripts.generate_neuro_dataset \
    --backend ollama:gemma4:31b --n-per-family 20 \
    --output data/cortex_train_v2.jsonl \
    --resume --supervised --log-file data/regen_v2.jsonl \
    > D:/cortex/logs/regen_v2_stdout.log 2>&1 &
```

## Discord vs. WhatsApp readiness

- **Discord**: most stable. Token already in `.env` per `mercury status`.
  Just needs the gateway up.
- **WhatsApp**: rides on the Pixel Fold's Google Fi number per spec, and
  the Pixel Fold has been **offline for 9 days** in the tailnet. Bring it
  back on tailnet first, then `mercury gateway up whatsapp`.
- **Telegram / Slack / Signal**: not configured.

## When the regen + retrain finish

Cortex v2 will be available as `cortex-gemma-4-e4b:v2` in Ollama. To make
that the texting model:

```sh
mercury model
# pick: ollama → cortex-gemma-4-e4b:v2
mercury gateway restart discord
```
