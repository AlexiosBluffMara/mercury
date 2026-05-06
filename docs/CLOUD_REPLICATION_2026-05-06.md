# Mercury Architecture — Local + Cloud Mirror

**Updated:** 2026-05-06
**Purpose:** Hackathon submission needs (a) the local stack we built, and (b) a documented cloud-mirror that lets us prove cost-per-request, latency, and failover behaviour for any judge who wants to evaluate scaling potential beyond a single Mac.

## TL;DR

| Tier | Local cost | Cloud cost (1k req/day) | Best for |
|------|-----------|-------------------------|----------|
| Inference (E4B / 26B / 31B) | $0 | **$8–60/mo** | Hybrid: local first, cloud on miss |
| Gateway (Mercury process) | $0 | $5–15/mo | Cloud must be always-on for bots |
| Persistence (sessions, vault) | $0 | $0–8/mo | Cloud free tiers cover MVP |
| Embeddings (`embeddinggemma:300m`) | $0 | $0–3/mo | Cloud free tier ample |
| **Total demo-day spend** | **$0** | **~$15–80/mo** | Whichever path is faster wins |

The point isn't to pick one tier — it's to prove the **same code routes through either**, and the failover graph degrades gracefully end-to-end.

## Reference local architecture (what we have today)

```
┌────────────────── Pixel Fold / iPhone / Web ───────────────────┐
│                      (clients & control surface)               │
└──────────────┬─────────────────────────────────────────────────┘
               │ Discord / WhatsApp / WebUI
               │
        ┌──────▼─────────────────────────────────────────┐
        │  Mercury Gateway (Python)                       │
        │  • dual-mode router (fast vs deep)              │
        │  • multi-platform adapters                      │
        │  • cortex-lights hook (Hue)                     │
        └──┬───────────────┬───────────────┬──────────────┘
           │               │               │
   ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼───────────┐
   │  Seratonin   │ │  Big Apple  │ │  Seratonin WSL2  │
   │  Win11+5090  │ │  M4 Max 48G │ │  Ubuntu 24+5090  │
   │ ┌──────────┐ │ │┌───────────┐│ │┌────────────────┐│
   │ │  Ollama  │ │ ││ mlx-vlm   ││ ││ vLLM 0.20      ││
   │ │  :11434  │ │ ││:8080 E4B  ││ ││ :8083          ││
   │ │ E4B/TRIBE│ │ ││:8081 26B  ││ ││ NVFP4 31B+MTP  ││
   │ └──────────┘ │ ││:8082 31B  ││ │└────────────────┘│
   │              │ │└───────────┘│ │                  │
   └──────────────┘ └─────────────┘ └──────────────────┘
       (CUDA)         (Metal/MLX)         (CUDA + MTP)

Persistence: ~/.mercury/state.db (SQLite), ~/.mercury/vault/ (markdown)
Lights:      WSL2 daemon polls ~/.cortex/lights-state.json → Hue API
```

Mercury already has all the routing primitives needed:
- `custom_providers` list — each with a `base_url` and `api_mode`
- `aliases` map — symbolic names (`fast`, `deep`, `tribe`, `audio`) bound to specific provider+model pairs
- `dual_mode` — auto-escalates fast→deep at >280 chars

To go cloud, we don't change Mercury — we just add new providers to the list and reorder the alias bindings.

## Cloud mirror — component-by-component

### 1. Inference layer

| Local | Cloud equivalent | Pricing notes |
|-------|------------------|---------------|
| Big Apple E4B (MLX, port 8080) | HF Inference Endpoint (T4) | $0.50/hr active, scale-to-zero idle |
| Big Apple 26B-A4B (MLX, port 8081) | HF Endpoint (L4 24GB) or Modal (L4) | HF $0.80/hr, Modal $0.50–1/hr |
| Big Apple 31B (MLX, port 8082) | HF Endpoint (A10G/A100) or Modal | HF 2×A100 $5/hr, Modal A100 $4.10/hr |
| Seratonin 31B + MTP (vLLM NVFP4) | Modal A100 with vLLM image | $4.10/hr active, scale-to-zero idle |
| Seratonin E4B / TRIBE (Ollama) | HF Endpoint (T4) | $0.50/hr |
| Per-token alternative | OpenRouter / Together | $0.06–0.45/M combined |

**Per-request cost math (typical 200-token reply on 31B):**
- Local: $0
- HF A100 endpoint, $5/hr ÷ ~6 req/min = **~$0.014/req**
- Modal A100, $4.10/hr ÷ ~6 req/min = **~$0.011/req**
- OpenRouter 26B paid, ~250 in + 200 out = **~$0.08/req** (slowest, but no provisioning)
- Together AI 26B = **~$0.05/req**

**Recommendation:** Cloud-mirror uses **Modal** for 31B (cheapest scale-to-zero A100), **HF Endpoints** for E4B/26B (boring, reliable), **OpenRouter free** as the cheapest backstop. Per-token pricing only for spike traffic.

### 2. Gateway layer (Mercury process)

| Local | Cloud equivalent | Pricing notes |
|-------|------------------|---------------|
| Python on Big Apple/Seratonin | **Fly.io** small VM | $5/mo, always-on, region-pinned |
| (alternate) | **Cloud Run with min-instances=1** | ~$15/mo always-on, scales up |
| (alternate) | **Modal background app** | $0.40/hr CPU, $0.04 idle |

**Why Fly.io for the bot process:** Discord and WhatsApp bots need a persistent WebSocket. Cloud Run can do it but the always-on requirement removes its scale-to-zero advantage. Fly.io's $5 small VM (256MB / shared CPU) is purpose-built for this and hits us in the right spot pricewise. **Recommended.**

### 3. Persistence

| Local | Cloud equivalent | Free tier? |
|-------|------------------|-----------|
| SQLite at `~/.mercury/state.db` | **Cloudflare D1** | 5 GB / 5M reads/day free |
| markdown vault `~/.mercury/vault/` | **Cloudflare R2** | 10 GB free, no egress fees |
| sessions cache | Cloudflare KV | 100k reads/day free |
| Discord thread map | D1 | included above |

**All three covered by free tier** for our traffic. If we exceed free tier, R2 is $0.015/GB-mo, D1 is $0.001/1k reads. Realistic monthly cost: **$0–3.**

### 4. Embeddings (`embeddinggemma:300m`)

| Local | Cloud equivalent | Pricing |
|-------|------------------|---------|
| Seratonin Ollama | **Cloudflare Workers AI** `@cf/baai/bge-large-en-v1.5` | First 10k neurons/day free, then $0.011/1k neurons |
| | HF Inference (T4) | $0.50/hr |
| | Modal (CPU) | $0.04/hr |

Workers AI ships embeddings as a free-tier product. **Cheapest cloud path is Workers AI** — though it's not literally Gemma's embedding model, the dimensionality and quality are comparable for our retrieval needs.

### 5. Cortex Hue lights

Not replicable in cloud — Hue requires a physical bridge on the LAN. The lights stay on the local-only path. Cloud failover doesn't include them; if local is down, no lights. That's acceptable: lights are observability, not a user-facing feature.

## Failover & load-balancing pattern

Mercury's `custom_providers` list is ordered. To add resilience we:

1. **Healthcheck loop** — every 30s ping each provider's `/v1/models` endpoint. If it 5xx's or times out, mark `unhealthy` for the next 60s.
2. **Tiered alias resolution** — when client asks for `fast`, walk the chain:
   ```
   fast = [
     ollama-local,                # Seratonin 5090, ~7ms LAN, $0
     mlx-bigapple-e4b,            # Big Apple, ~12ms LAN, $0
     ollama-bigapple,             # Big Apple Ollama fallback, $0
     vllm-cloud-modal-l4,         # Modal L4 cloud, ~80ms WAN, $0.50/hr
     openrouter-free,             # rate-limited free tier, $0
     openrouter-paid              # paid, $0.06+0.33/M
   ]
   ```
3. **Round-robin within tier** — if both Big Apple ports respond, alternate.
4. **Circuit breaker** — after 3 consecutive failures on the same provider, skip it for 5 minutes; halve that timeout each successful retry until it returns to active.
5. **Cost-aware routing** — when Mercury is in "cost-saver" mode (config flag), only use free tiers and refuse paid fallback. Otherwise it'll burn cents trying to be helpful while you're sleeping.

## What it would take to replicate the architecture in cloud

### Phase 1 — minimum viable mirror (~2 hours' work)
1. **Modal** account (no GCP credit card needed). Push a single FastAPI app that wraps `vllm.entrypoints.openai.api_server` with `--speculative-model google/gemma-4-31B-it-assistant`. Deploy. **Cost: $4.10/hr active, $0 idle**.
2. **Fly.io** machine in `iad` region running the existing Mercury Python image. Discord/WhatsApp env vars from `~/.mercury/.env`. **Cost: $5/mo.**
3. **Cloudflare D1 + R2 + KV** — provision via `wrangler d1 create`, `wrangler r2 bucket create`, `wrangler kv namespace create`. Mercury already has the API skeleton; flip a config flag from `sqlite:./state.db` → `d1://abm-isu/mercury_state`. **Cost: $0 in free tier.**
4. Update `~/.mercury/config.yaml`:
   ```yaml
   custom_providers:
     - name: ollama-local                        # tier 0
       base_url: http://localhost:11434/v1
     - name: mlx-bigapple-e4b                    # tier 1 LAN
       base_url: http://100.93.240.52:8080/v1
     - name: vllm-modal-31b                       # tier 2 WAN
       base_url: https://soumit--mercury-vllm.modal.run/v1
       key_env: MODAL_TOKEN_ID
     - name: openrouter-free                      # tier 3 backstop
       base_url: https://openrouter.ai/api/v1
       key_env: OPENROUTER_API_KEY
   ```
5. Add the healthcheck loop to `gateway/router.py`. ~50 LOC. The circuit-breaker is one decorator.

### Phase 2 — multi-region (post-deadline)
- Modal regions: `us-east`, `eu-central`, `ap-south` for sub-100ms anywhere.
- Cloudflare Tunnel from each Big Apple/Seratonin so a phone in Bloomington still gets <50ms hits to the LAN.
- DNS-based georouting: `mercury.redteamkitchen.com` → Cloudflare Workers that pick the nearest backend.

### Phase 3 — actual Google primitives (also post-deadline)
- **Cloud Run with GPUs** — went GA in 2026, supports L4 at ~$0.60/hr. Could replace Modal if we want to stay all-Google.
- **Vertex AI Endpoints** — currently off-limits per the May 1 incident; would need governance review before ever turning back on.
- **GKE Autopilot** — overkill for this scale.

## Why this hybrid architecture is "good"

1. **Zero marginal cost path stays available.** 95%+ of traffic is local LAN. The cloud provider is the anti-bus-factor, not the workhorse.
2. **Latency floor** — local hits respond in 10–50ms. Cloud A100 starts cold at ~8s warm-up but warm at 80ms. Mercury's router prefers warm local before cold cloud.
3. **Throughput ceiling.** When 50 students hammer the demo simultaneously, local saturates first; Modal scales horizontally on demand within seconds.
4. **Failure isolation.** If WSL2 crashes, MLX still serves. If Big Apple's launchd dies, Seratonin Ollama covers. If both LAN nodes are off, Modal/HF picks up. If Modal's region is down, OpenRouter free tier picks up. If the entire internet is down, Pixel Fold's local NPU + offline Discord client still works.
5. **Cost predictability.** Demo day at 1k requests bursts to ~$0.50 of cloud spend then quiets back to free-tier baseline.
6. **Audit trail for judges.** Every request's provider chain is logged in `~/.mercury/state.db` (or D1 in cloud), so we can show "this 31B answer was served by Big Apple in 2.1s for $0; this fallback was Modal in 0.4s for $0.011."

## Sources

- [HuggingFace Inference Endpoints pricing](https://huggingface.co/docs/inference-endpoints/pricing)
- [Modal pricing — pay-per-second GPU](https://modal.com/pricing)
- [Cloudflare D1 / R2 / KV free tiers](https://developers.cloudflare.com/workers/platform/pricing/)
- [Fly.io machine pricing](https://fly.io/docs/about/pricing/)
- [OpenRouter Gemma 4 26B-A4B pricing](https://openrouter.ai/google/gemma-4-26b-a4b-it)
- [Cloud Run with GPUs (2026)](https://cloud.google.com/run/docs/configuring/services/gpu)
