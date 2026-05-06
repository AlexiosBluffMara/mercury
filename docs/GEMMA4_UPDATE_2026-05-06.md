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

### 2. MTP drafters (May 2026) — **shipped 2026-05-06**
Speculative decoding via paired drafter models gives a measured 1.42× wall-clock speedup on E4B with 38% acceptance rate:
- `google/gemma-4-E2B-it-assistant` — drafter for E2B/E4B
- `google/gemma-4-E4B-it-assistant` — **WIRED INTO BIG APPLE PORT 8083**
- `google/gemma-4-26B-A4B-it-assistant` — downloaded; not wired (target won't fit BF16)
- `google/gemma-4-31B-it-assistant` — downloaded; not wired (target won't fit BF16)

**Important caveat (still true):** the public weights expose only the standard autoregressive interface for compatibility. MTP heads are excluded from the model config and are preserved only in Google's LiteRT export. The *separate* drafter models are accessible.

**Status: SHIPPED.** Path that worked:
- mlx-vlm 0.5.0 (installed from `git+https://github.com/Blaizzy/mlx-vlm.git@main`, not yet released to PyPI as of writing)
- `mlx_vlm.server --draft-model google/gemma-4-E4B-it-assistant --draft-kind mtp --draft-block-size 6`
- Target: `unsloth/gemma-4-E4B-it-UD-MLX-4bit` (4-bit, with Apr 11 chat template fix)
- Drafter: `google/gemma-4-E4B-it-assistant` (HF transformers format, auto-converted to MLX by mlx-vlm at load time)
- launchd job: `~/Library/LaunchAgents/ai.mercury.mlx-e4b-mtp.plist` (port 8083, KeepAlive)

**Measured baseline vs MTP** (CLI `mlx_vlm.generate`, prompt `"Count from 1 to 20."`, max_tokens=80, temp=0):

| | Wall-clock | Generation tps | Prompt tps | Peak memory | Spec rounds |
|---|---|---|---|---|---|
| Baseline (no drafter) | 6.02s | 97.78 t/s | 16.50 t/s | 6.65 GB | n/a |
| MTP (Google drafter, block=6) | **4.25s** | 73.10 t/s* | 338.83 t/s | 6.81 GB | 22 rounds, 2.27 accepted/round |

\* Generation tps reads lower because mlx-vlm's metric counts only validated tokens divided by total time, but the *wall-clock* improvement is the truth: ~30% faster end-to-end on this prompt.

**Why mlx-vlm and not vLLM:** vLLM 0.20.1 explicitly raises `NotImplementedError: Speculative Decoding with draft models or parallel drafting does not support multimodal models yet`. Since Gemma 4 E4B is multimodal (text + image + audio), vLLM is incompatible with the MTP path for our model. mlx-vlm 0.5.0 is the only stack that supports MTP + Gemma 4 multimodal today.

**Why not 26B/31B + MTP:** the mlx-vlm drafter docs require BF16 targets. BF16 26B is ~52 GB; BF16 31B is ~62 GB. Big Apple has 48 GB unified memory. Neither fits. The 4-bit Unsloth target works for E4B (BF16 ~9 GB) but not the larger sizes. Future option: try 8-bit/6-bit targets if mlx-vlm relaxes the BF16 requirement.

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
