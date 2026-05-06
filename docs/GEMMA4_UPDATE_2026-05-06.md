# Gemma 4 Update Assessment — 2026-05-06

## Summary

Google has shipped two material patches to Gemma 4 since its initial release. We're upgrading our entire stack (Big Apple MLX + Seratonin Ollama) to pick up the fixes and prepare for MTP speculative decoding.

## Release timeline

| Date | Release | What changed |
|------|---------|--------------|
| 2026-03-31 | Gemma 4 launch | E2B, E4B, 26B-A4B, 31B with 256K context, native vision/audio |
| 2026-04-11 | **Chat template fix + llama.cpp fixes** | Corrected tokenizer template; affects all sizes |
| 2026-04-16 | Gemma 4-MTP | Multi-token-prediction variants released |
| 2026-05-06 | **MTP drafter models** (`google/gemma-4-{size}-it-assistant`) | Up to 3× speedup via speculative decoding |

Sources:
- [Google AI Releases](https://ai.google.dev/gemma/docs/releases)
- [Unsloth Gemma 4 docs](https://unsloth.ai/docs/models/gemma-4)
- [Google blog: MTP drafters](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/)

## What this means for our stack

### 1. Chat template fix (April 11) — **critical**
Pre-April-11 weights had a chat-template bug that affects multi-turn correctness. All Unsloth `*-UD-MLX-4bit` and `*-MLX-8bit` repos now ship the corrected template. We need to refresh:

| Model | Current source | New source | Action |
|-------|----------------|------------|--------|
| E4B (Big Apple) | `unsloth/gemma-4-E4B-it-UD-MLX-4bit` | same | already current — re-pulled to verify SHA |
| 26B (Big Apple) | `mlx-community/gemma-4-26b-a4b-it-4bit` | `unsloth/gemma-4-26b-a4b-it-UD-MLX-4bit` | **upgrading** |
| 31B (Big Apple) | (not deployed) | `unsloth/gemma-4-31b-it-UD-MLX-4bit` | **new — first deployment** |
| E4B (Seratonin Ollama) | `gemma4:e4b` | same registry tag | re-pulled |
| 31B (Seratonin Ollama) | `gemma4:31b` | same registry tag | re-pulled |

### 2. MTP drafters (May 2026) — opt-in optimization
Speculative decoding via paired drafter models gives ~3× tokens/sec without quality loss:
- `google/gemma-4-E2B-it-assistant` — drafter for E2B/E4B
- `google/gemma-4-E4B-it-assistant`
- `google/gemma-4-26B-A4B-it-assistant`
- `google/gemma-4-31B-it-assistant`

**Important caveat:** the public weights expose only the standard autoregressive interface for compatibility. MTP heads are excluded from the model config and are preserved only in Google's LiteRT export. This means MTP inside the *base* model isn't accessible from MLX/Ollama — but the *separate* drafter models are.

**Status:** mlx_vlm.server (our serving layer on Big Apple) doesn't yet expose `--draft-model`. mlx-lm does. To benefit we'd need to either (a) wait for mlx_vlm to add drafter support, (b) switch 31B to mlx-lm + custom HTTP shim, or (c) use Ollama on Seratonin which now supports drafters. Deferred until after the Gemma 4 Good submission (May 18). Tracked as future work.

## Topology after this update

```
                     ┌─────────────────────────────────────┐
                     │  Mercury Gateway (router)           │
                     └────────────────┬────────────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            │                                                   │
   ┌────────▼─────────┐                              ┌──────────▼──────────┐
   │  Seratonin (5090) │                              │  Big Apple (M4 Max) │
   │  Ollama :11434    │                              │  MLX VLM servers    │
   ├──────────────────┤                              ├─────────────────────┤
   │ gemma4:e4b  FAST │  ← dual_mode.fast            │ E4B :8080  AUDIO   │  ← multimodal aux
   │ cortex-gemma-4-  │                              │ 26B :8081  MoE     │
   │ e4b      TRIBE   │                              │ 31B :8082  DEEP    │  ← dual_mode.deep
   │ embeddinggemma   │                              │ ollama  fallback    │
   └──────────────────┘                              └─────────────────────┘
```

## Verification matrix

| Check | Command | Pass criteria |
|-------|---------|---------------|
| BA E4B | `curl -s 100.93.240.52:8080/v1/models` | returns `unsloth/gemma-4-E4B-it-UD-MLX-4bit` |
| BA 26B | `curl -s 100.93.240.52:8081/v1/models` | returns `unsloth/gemma-4-26b-a4b-it-UD-MLX-4bit` |
| BA 31B | `curl -s 100.93.240.52:8082/v1/models` | returns `unsloth/gemma-4-31b-it-UD-MLX-4bit` |
| Sera E4B | `curl -s localhost:11434/api/show -d '{"name":"gemma4:e4b"}'` | `modified_at >= 2026-05-06` |
| Sera 31B | `curl -s localhost:11434/api/show -d '{"name":"gemma4:31b"}'` | `modified_at >= 2026-05-06` |
| Mercury fast | one-shot prompt via Mercury TUI | hits Seratonin E4B, ~150 tok/s |
| Mercury deep | prompt > 280 chars | escalates to Big Apple 31B |
| Mercury TRIBE | `mercury -m tribe` | hits cortex-gemma-4-e4b |

## Files changed

- `~/.mercury/config.yaml` (Seratonin) — model aliases + dual_mode targets
- `/Users/soumitlahiri/mlx-serve/start.sh` (Big Apple) — added 31b case, switched 26b to Unsloth UD-MLX-4bit
- `/Users/soumitlahiri/Library/LaunchAgents/ai.mercury.mlx-31b.plist` (Big Apple) — new launchd job
- `~/.cache/huggingface/hub/` (Big Apple) — fresh download of 31B and 26B (~36 GB)

## Outstanding follow-ups

- [ ] Add Apple Watch / iPhone shortcut hitting `mercury -m tribe` for the demo.
- [ ] When `mlx_vlm` ships drafter support, wire `google/gemma-4-31B-it-assistant` to port 8082 for the 3× speedup.
- [ ] Pull the matching drafter via Ollama on Seratonin once the Ollama registry exposes `gemma4-assistant:*` tags.
- [ ] Add a daily smoke-test cron that hits all three MLX ports + Seratonin Ollama and pings if anything 5xxs.
