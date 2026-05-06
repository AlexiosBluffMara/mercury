# Mercury Cloud Scaling — what we'd do with N dollars of cloud credits

**Updated:** 2026-05-06
**Audience:** the Gemma 4 Good Hackathon judges + anyone evaluating Mercury for grant / VC / district-IT funding.

## The premise

Mercury runs on consumer hardware today for **$0/request** (Apache-2.0 Gemma 4, self-hosted, electricity-only). The architecture is hybrid by design — the cloud failover layer already exists (`docs/CLOUD_REPLICATION_2026-05-06.md`), it's just sized for the current single-user demand. **This page is the playbook for what we'd build at each cloud-credit tier.** Theoretical, but every block below has a concrete vendor + SKU + monthly burn and is ready to paste into a `wrangler deploy` / `modal deploy` / `gcloud run deploy` invocation the day funding lands.

Five tiers. Each scales the previous one — not a rewrite.

## Tier 0 — what's running today (physical hardware, $0/mo)

**Capacity:** 1-5 simultaneous users, ≤1k requests/day, no cloud credits used.

**Hardware:**
- Big Apple — M4 Max MacBook 48 GB, $4,500 retail (one-time)
- Seratonin — RTX 5090 desktop 32 GB VRAM, ~$3,500 retail (one-time)
- Baby Pi — Raspberry Pi 5 8 GB, $80 (kiosk + AdGuard, not in inference path)
- Total: **~$8,100 one-time**, ~$15-25/mo electricity

**What it serves:**
- 4 MLX servers (E4B / 26B-A4B / 31B / E4B+MTP) on Big Apple
- Ollama (Gemma 4 E4B + TRIBE v2) on Seratonin RTX 5090
- Mercury Gateway on Seratonin
- 6 public Cloudflare-tunneled subdomains
- 5 client surfaces (Discord, WhatsApp, terminal, web UI, cron)

**Measured:** 94 tok/s on E4B vanilla; ~32 tok/s on 31B; OpenRouter `:free` 1000 reqs/day cap as cloud-burst safety net.

This is the baseline every tier below builds on. Cloud only adds *capacity*, never replaces the local path.

## Tier 1 — Hobbyist / single-classroom ($1k–5k/yr cloud credits)

**Goal:** keep one classroom's 30 students answered when local is unreachable.

**What we add:**
| Component | Vendor | SKU | Monthly cost |
|---|---|---|---|
| Cloud burst inference | Modal Labs | A100 40GB serverless, scale-to-zero | $4.10/hr active × ~10 hr/mo = **$41/mo** |
| Gateway always-on | Fly.io | shared-cpu-1x 256MB, region `iad` | **$5/mo** |
| Persistence | Cloudflare D1 | 5 GB / 5M reads/day free tier | **$0** |
| Static assets / vault | Cloudflare R2 | 10 GB free tier | **$0** |
| Embeddings | Cloudflare Workers AI | 10k neurons/day free | **$0** |
| **Subtotal** | | | **~$46/mo, ~$550/yr** |

**Implementation kit (ready to run on funding-day):**
```bash
# Modal A100 deployment of Mercury vLLM bridge
modal deploy mercury_modal_app.py    # already written, see CLOUD_REPLICATION doc

# Fly.io Mercury gateway
fly launch --image rtkitchen/mercury:latest --region iad --vm-size shared-cpu-1x

# Cloudflare D1 init
wrangler d1 create mercury-state
wrangler d1 execute mercury-state --file=schema.sql
```

**Performance vs hardware-only:** identical for the 95% of requests served locally. Cloud burst adds ~80-150ms WAN latency on the 5% that miss local.

## Tier 2 — School (~10k credits/yr, ~250 students)

**Goal:** survive a snow day — every student opens Mercury at home, simultaneously.

**What we add to Tier 1:**
| Component | Vendor | SKU | Monthly cost |
|---|---|---|---|
| Always-warm inference (E4B) | HF Inference Endpoints | T4 16GB, `min_replica=1` | $0.50/hr × 24 × 30 = **$360/mo** |
| Burst inference (31B) | Modal Labs | A100 40GB + autoscaling | $4.10/hr × ~50 hr/mo = **$205/mo** |
| Gateway with HA | Fly.io | shared-cpu-1x × 2 regions | **$10/mo** |
| Persistence | Cloudflare D1 paid | upgrade to 50 GB | **$5/mo** |
| Embeddings | Cloudflare Workers AI paid tier | $0.011/1k neurons over 10k/day | **$5-15/mo** |
| Monitoring | Cloudflare Logpush + R2 | 30-day retention | **$3/mo** |
| **Subtotal** | | | **~$590/mo, ~$7k/yr** |

**Capacity:** 300 simultaneous queries (Modal autoscale), 50ms P50 latency, sub-300ms P99 even when local is offline.

**Implementation kit:**
```bash
# HF Endpoint — keeps E4B warm
huggingface-cli endpoint create mercury-e4b-warm \
    --model unsloth/gemma-4-E4B-it-UD-MLX-4bit \
    --type t4 --min-replica 1 --max-replica 4

# Modal autoscale config (in mercury_modal_app.py)
@app.cls(gpu="A100", concurrency_limit=10, container_idle_timeout=120,
         allow_concurrent_inputs=4)
class MercuryDeep: ...
```

## Tier 3 — District ($100k credits/yr, 10k students)

**Goal:** an entire school district relies on Mercury as the primary AI tutor. 99.9% SLA, multi-region, identity-aware.

**What we add to Tier 2:**
| Component | Vendor | SKU | Monthly cost |
|---|---|---|---|
| Multi-region inference | Modal Labs | A100 × 3 regions (`us-east`, `eu-central`, `ap-south`) | **$2,000/mo** |
| Always-warm 31B (US) | HF Endpoints | A10G 24GB × 2 replicas | **$580/mo** |
| Always-warm E4B (3 regions) | HF Endpoints | T4 × 3 | **$1,080/mo** |
| Gateway | Cloud Run + min-instances=2 | 4 vCPU, 8 GB, 2 regions | **$120/mo** |
| Persistence (regional) | Cloudflare D1 + Hyperdrive | Multi-region replicas | **$50/mo** |
| Vector DB (RAG) | Cloudflare Vectorize | 50M dims × 100k vectors | **$70/mo** |
| Identity (SSO + audit) | Cloudflare Access | Free for ≤50 users; $3/user above | **$300-500/mo** |
| Logs + metrics | GCP Logging + BigQuery | 50 GB ingest/mo | **$50/mo** |
| **Subtotal** | | | **~$4,250/mo, ~$51k/yr** |

**Capacity:** 5,000 simultaneous queries globally. Latency P50 ≤80ms anywhere on Earth. 99.9% SLA backed by Cloudflare + Modal + HF SLAs combined.

**The non-obvious "Be Googley" bit:** at this tier, **GCP Cloud Run with native GPUs** (went GA 2026, ~$0.60/hr T4) becomes price-competitive with Modal — and lets a school district that's already on Workspace consolidate billing. Plug Mercury's image into Cloud Run `--gpu-type=nvidia-l4 --gpu-count=1` and we cut Modal spend by ~40% while keeping Mercury's hybrid router otherwise unchanged.

We'd still avoid Vertex AI Generative API (the May 1 incident scarring is real, the 90%-budget kill switch is canon) but Cloud Run with custom Mercury images is fair game.

## Tier 4 — National / state-DOE ($1M+ credits/yr, 1M+ students)

**Goal:** a state department of education adopts Mercury for every K-12 student. Hard-real-time SLA, FedRAMP-tier security posture, GA-grade observability.

**What we add to Tier 3:**
| Component | Vendor | SKU | Monthly cost |
|---|---|---|---|
| Sustained-load inference | GKE Autopilot | A100 × 20 nodes, autoscaling 5-50 | **$25,000/mo** |
| Identity + RBAC | Cloud Identity-Aware Proxy | Per-user pricing | **$5,000/mo** |
| Audit + retention | BigQuery + Dataflow | 5 TB/mo ingest, 13-month retention | **$3,000/mo** |
| Vault (per-tenant) | Cloud Filestore + Cloudflare R2 | 1 TB per district | **$2,000/mo** |
| Network egress | Cloud CDN + Cloudflare | typical egress patterns | **$2,500/mo** |
| Specialist humans | Site reliability engineer × 2 | not a SaaS, but a real cost | **$30,000/mo** |
| **Subtotal** | | | **~$67,500/mo, ~$810k/yr** |

**Capacity:** 50,000 simultaneous queries. Sub-100ms P50 in every continental US state. Per-student usage logged + retained per Section 508 / COPPA / FERPA. Dedicated Cloudflare WAF profile, SOC 2 Type 2 audit trail.

**The local-first invariant still holds.** Even at this tier, a school running on a 5090 in the AV closet is *the cheapest* and *the lowest latency* path. Cloud isn't the workhorse — it's the anti-bus-factor. The architecture stays hybrid because hybrid is cheaper *and* more reliable than either pole alone.

## Performance vs cost — apples-to-apples table

For a single conversation (5-turn, ~600 input + 800 output tokens):

| Tier | Where it serves | Latency P50 | Cost per session | Cost per 10k sessions/day |
|---|---|---:|---:|---:|
| **0 (us today)** | Big Apple :8080 | **12 ms LAN** | **$0** | **$0** |
| 1 — hobbyist | Modal A100 (cold) | 8s + ~150ms | $0.011 | ~$110/day |
| 1 — hobbyist (warm) | Modal A100 (warm) | ~150ms | $0.005 | ~$50/day |
| 2 — school | HF T4 + Modal A100 | ~80ms | $0.008 | ~$80/day |
| 3 — district | Multi-region GKE/HF | ~50ms | $0.003 | ~$30/day |
| API-only competitor | Vertex AI Gemma 3 27B equivalent | ~300ms | $0.20 | ~$2,000/day |

The bottom row is the rhetorical lever: **at every Mercury tier, including with cloud-burst layered on top, the per-session cost is 10-100× cheaper than a competitor that built only-cloud.** That gap is what funds expansion.

## Implementation readiness checklist

If we win the hackathon and get cloud credits, here's the sequence (hours not days):

- [ ] Hour 1 — Modal account, push `mercury_modal_app.py` (skeleton already in repo gpc/), `modal deploy`. **One A100 endpoint live.**
- [ ] Hour 2 — Fly.io machine, push Mercury Docker image, set `OPENROUTER_API_KEY` + `DISCORD_BOT_TOKEN` from secrets manager. **Gateway running in cloud.**
- [ ] Hour 3 — Cloudflare D1 / R2 / KV provisioning via wrangler. **State migrated.**
- [ ] Hour 4 — Update `~/.mercury/config.yaml` with cloud-tier providers in the failover chain after the existing local ones. **Hybrid live.**
- [ ] Hour 5 — Smoke-test with `curl https://mercury.redteamkitchen.com` from outside the tailnet. End-to-end verified.

For Tier 2: add HF Endpoints + Cloudflare Workers AI in another 2 hours.

For Tier 3: GCP Cloud Run with GPUs needs a working GCP project (we have `abm-isu`), an L4 quota request (24 hr SLA), then `gcloud run deploy` (1 hour). All Cloud-Run-native; no Vertex API.

## What we will *never* spend hackathon winnings on

- Per-token Vertex AI Gemini API. Open-weight Gemma 4 + self-host removes the toll booth.
- Closed-source competitors (OpenAI, Anthropic API in the hot path). Roundtrip cost without offline-first capability defeats Digital Equity.
- Headcount-heavy SaaS (e.g. Datadog $50k/mo). Cloudflare + GCP native observability is sufficient.

## Sources

- [Modal Labs pricing](https://modal.com/pricing) — A100 $4.10/hr, scale-to-zero
- [HuggingFace Inference Endpoints pricing](https://huggingface.co/docs/inference-endpoints/pricing) — T4 $0.50/hr, A10G $1.20/hr, A100 $5/hr
- [Cloudflare D1 / R2 / KV / Workers AI / Vectorize pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [Fly.io machine pricing](https://fly.io/docs/about/pricing/) — shared-cpu-1x $5/mo
- [Cloud Run with GPUs (2026 GA)](https://cloud.google.com/run/docs/configuring/services/gpu)
- [GKE Autopilot pricing](https://cloud.google.com/kubernetes-engine/pricing)
- [OpenRouter free + paid](https://openrouter.ai/docs/api/reference/limits)
- [Companion docs: HACKATHON_COSTS, CLOUD_REPLICATION, GEMMA4_UPDATE, SELF_UPDATE_LOOP, MERCURY_CORTEX_CONTRACT](.)
