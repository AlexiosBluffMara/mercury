# Financial Breakdown — ABM × Illinois State University Research Stack

*Decision-ready cost memo. Last priced: 2026-05-01. All numbers verified against vendor pricing pages on the date above (see Sources). Prices in USD.*

---

## 1. TL;DR

- **Local-first wins by a wide margin.** The RTX 5090 already in hand serves Mercury chat, Mercury reasoning, and Cortex inference at electricity-only cost (~$0.09/hour, ~$5–10/month at typical research duty cycles). Every dollar shifted off this GPU and onto a hosted API is a regression at our current scale.
- **Hosted bursting goes through OpenRouter, not Vertex.** When the 5090 is busy with TRIBE v2 fMRI inference, Mercury falls back to **Gemma 4 26B A4B on OpenRouter** at $0.06/$0.33 per 1M tokens — already wired in `agent/auxiliary_client.py` as the priority-1 router. There is currently no first-party Gemma 4 SKU on AI Studio or Vertex (Gemma 3 only); OpenRouter is the only hosted Gemma 4 path.
- **Internet grounding stack: Tavily (free 1,000/mo) + Firecrawl ($16/mo Hobby, already configured)** with Brave $5/1k as paid overflow. Avoid Gemini's hosted grounding except for the 1,500 free Pro requests/day — it's $35/1k after that, the most expensive option on the table.
- **Break-even line: the 5090 stays cheapest up to ~50–80 simultaneously active human users.** Past that, the GPU saturates and a Gemma-on-OpenRouter (or Together) burst tier wins on per-token economics. Until then, every API dollar is wasted.
- **Sign up THIS WEEK:** **HuggingFace Pro ($9/mo)** for ZeroGPU access (25 min/day H200) — replaces our Cloud Run plan for the public Cortex demo at ~1% of the cost — and apply for an **ACCESS-CI EXPLORE allocation** (free, one-page abstract, decided in days) for HPC headroom before the Maximize cycle opens June 15.

---

## 2. The Five Workload Types

Assumes the 5090 runs Gemma 4 E4B (text/vision) and Gemma 4 26B-MoE (audio + reasoning) via Ollama. Per-request token shapes are real-world averages from Mercury's session logs and Cortex's narration spec.

| Workload | Typical Volume | Latency Need | Cost-Optimal Provider TODAY | Cost / Unit | $/mo @ 1k req/day | $/mo @ 10k req/day |
|---|---|---|---|---|---|---|
| **Mercury chat** (Discord/web, ~400 in / 200 out) | High freq, bursty | <2s first token | Ollama on 5090 (E4B) | electricity only | **~$3** electricity | **~$8** electricity |
| **Mercury chat** (cloud burst) | — | — | OpenRouter Gemma 4 26B A4B | $0.06/$0.33 per 1M | $3.40/mo | $34/mo |
| **Mercury `/long` reasoning** (~6k in / 2k out, 26B MoE) | Low freq | <10s ok | Ollama on 5090 (26B-MoE) | electricity only | **~$2** electricity | **~$15** electricity |
| **Mercury `/long` cloud burst** | — | — | Gemini 2.5 Flash | $0.30/$2.50 per 1M | $5.40/mo | $54/mo |
| **Mercury multimodal** (image+audio, ~8k in / 800 out) | Medium freq | <5s ok | 5090 (26B-MoE for audio, E4B for vision) | electricity only | **~$3** | **~$10** |
| **Mercury multimodal cloud burst** | — | — | Gemini 2.5 Flash (multimodal native) | $0.30/$2.50 + $0.0010/img | $9/mo | $90/mo |
| **Cortex narration** (3.2k in / 1.4k out × 4 personas = 12.8k in / 5.6k out per scan) | ~10 scans/day | <30s ok | OpenRouter Gemma 4 26B A4B | $0.06/$0.33 per 1M | **$78/mo** at 10 scans/day | $780/mo at 100 |
| **Cortex narration (local)** | — | — | 5090 (E4B per persona) | electricity only | **~$2** electricity | ~$20 |
| **Cortex TRIBE v2 inference** (brain foundation model, ~8B params, single fMRI volume = ~30s GPU time) | 5–20 scans/day | <60s | **5090 (mandatory — no API equivalent)** | electricity only | ~$1.50 | ~$15 |

**Key takeaway:** at 1k requests/day, total local cost is ~$10/month electricity. Equivalent hosted cost is ~$25–110/month. The 5090 buys us a 3–10× factor before scale forces us off it.

---

## 3. Gemma Hosted API Options — Real Numbers

Gemma 4 launched April 2026; provider availability is patchier than Gemma 3. Where Gemma 4 isn't carried, Gemma 3 27B is the closest price proxy.

| Provider | Gemma SKU | Input ($/1M) | Output ($/1M) | Billing Model | Notes |
|---|---|---|---|---|---|
| **OpenRouter** | Gemma 4 26B A4B IT | $0.06 | $0.33 | Per-token | Already wired in `auxiliary_client.py`; aggregates DeepInfra/Together |
| **OpenRouter** | Gemma 4 31B IT | $0.13 | $0.38 | Per-token | Dense variant; pricier |
| **OpenRouter** | Gemma 4 26B A4B (free) | $0.00 | $0.00 | Rate-limited | Free tier; usable for pre-demo dev |
| **OpenRouter** | Gemma 3 27B (free) | $0.00 | $0.00 | Rate-limited | Stable, well-supported |
| **DeepInfra** | Gemma 3 27B IT | $0.08 | $0.16 | Per-token | Cheapest dense Gemma 3; no Gemma 4 yet listed |
| **DeepInfra** | Gemma 3 12B IT | $0.04 | $0.13 | Per-token | Smallest dense variant |
| **DeepInfra** | Gemma 3 4B IT | $0.04 | $0.08 | Per-token | E4B-class price proxy |
| **Together.ai** | Gemma 3 27B | ~$0.20 | ~$0.20 | Per-token | More expensive than DeepInfra |
| **Fireworks.ai** | Gemma 3 27B | ~$0.20 | ~$0.20 | Per-token Serverless | Comparable to Together |
| **Google AI Studio (Gemini API)** | Gemma 4 | **NOT YET LISTED** | — | — | Gemma 3 yes, Gemma 4 not yet on the public Gemini API as of 2026-05-01 |
| **Vertex AI Model Garden** | Gemma 4 (deploy-as-endpoint) | A100: $3.37/hr | — | Per-second VM | Gemma 4 deployable but billing is GPU-time, not tokens. ~$2,400/mo always-on |
| **Replicate** | Gemma 3 27B | ~$0.0002–0.0011/sec L40S | — | Per-second GPU | BYO Gemma 4 via custom model |
| **Modal** | BYO Gemma 4 | L4: $0.000222/s ($0.80/hr); A100-80: $0.000694/s ($2.50/hr); L40S: $0.000542/s ($1.95/hr); H100: $0.001097/s ($3.95/hr) | — | Per-second, scale-to-zero | Best serverless GPU pricing for BYO Gemma 4 |
| **RunPod Serverless** | BYO Gemma 4 | A100-80: ~$2.31–2.72/hr; H100-80: ~$3.55–4.18/hr | — | Per-second | Cold-start ~5–15s; cheaper Community Cloud at $0.89/hr A100 |
| **Lambda Labs** | BYO Gemma 4 | A100-80: $1.29/hr; H100 PCIe: $2.49/hr; H100 SXM: $2.89–3.78/hr | — | Hourly on-demand | Cheapest reserved A100/H100 |
| **Anyscale Endpoints** | — | — | — | — | **Shut down** — Anyscale pivoted to platform-only post 2024; no public Gemma SKU |
| **HuggingFace Inference Providers** | Gemma 3 27B (routed) | Provider-cost passthrough; Pro tier 2M credits/mo | — | Per-token | $9/mo Pro = ~2M tokens of Gemma 3 27B |
| **HuggingFace Inference Endpoints (dedicated)** | BYO Gemma 4 | L4: $0.80/hr; A10G: $1.00/hr; A100-80: $2.50/hr | — | Per-minute, billed hourly | Same SKUs as Modal but no scale-to-zero |
| **Groq** | Gemma 3 9B | $0.05–0.10 / $0.10 per 1M | — | Per-token, LPU | **No Gemma 4 yet**. Gemma 3 9B at ~$0.10/1M is fastest on planet (~800 tok/s) |
| **Cerebras** | Gemma 3 (limited) | Public pricing not yet posted for Gemma | — | Per-token | Sales-managed for higher-tier; not for solo developers |
| **OpenRouter (free tier proxy)** | Llama 3.1 8B (free) | $0.00 | $0.00 | Rate-limited | Useful price proxy for E4B-scale cloud workloads |

**Recommendation:** Stay on OpenRouter Gemma 4 26B A4B at $0.06/$0.33 for cloud burst. Mercury already routes through it. If we ever exceed ~50M tokens/month, switch to Modal-hosted BYO at L40S ($1.95/hr × 24 × 30 = $1,400/mo always-on, but scale-to-zero brings this to ~$200–300/mo at typical duty cycle).

---

## 4. Gemini 2.5 / 3.x Pricing & Features

| SKU | Input ($/1M) | Output ($/1M) | Cached Input | Multimodal Image | Grounding | Notes |
|---|---|---|---|---|---|---|
| **Gemini 3.1 Pro** | $2.00 (≤200K), $4.00 (>200K) | $12.00 (≤200K), $18.00 (>200K) | $0.20 (90% off) | included in input | $14/1k after 1,500/day free | Long-context cliff at 200K |
| **Gemini 3 Flash** | $0.50 | $3.00 | $0.05 (90% off) | included | $14/1k after free | 1M context |
| **Gemini 2.5 Pro** | $1.25 (≤200K), $2.50 (>200K) | $10.00 (≤200K), $15.00 (>200K) | $0.13 (90% off) | included | $35/1k after 1,500/day free | Same context cliff |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | $0.075 (75–90% off) | included | $35/1k after 500/day free | 1M context, fastest cheap multimodal |
| **Gemini 2.5 Flash-Lite** | ~$0.10 | ~$0.40 | implicit caching | included | $35/1k | Cheapest multimodal Gemini |
| **Gemini Live API** | per-token + audio surcharge | — | — | — | — | For real-time voice; not a Mercury priority |
| **Cache storage** | $4.50/M tokens/hr (Pro), $1.00 (Flash) | — | — | — | — | Required to hold the cache; hourly billed |

**Feature notes that matter for Mercury:**

- **Tool/function calling** is billed identically to a normal call — no surcharge, but the tool result's tokens count toward input.
- **Implicit caching is on by default since May 2025** — repeated prefixes (system prompt, fixed brief) auto-discount at 75–90% with no code change.
- **Grounding-with-Google-Search at 1,500 Pro / 500 Flash free requests/day** is genuinely free in practice for our hackathon scale; past that it's the most expensive search option in section 5.

**Where Gemini wins for ABM × ISU:** Gemini 2.5 Flash-Lite ($0.10/$0.40) is cheaper than the cheapest hosted Gemma 4 today *and* multimodal-native. For occasional cloud-burst multimodal where image-in is the bottleneck, this beats running E4B-vision on the 5090 only because it skips the round-trip.

---

## 5. Internet Grounding Stack for the Local 5090

Goal: give the local Gemma 4 deployment a real-web tool without paying Gemini's $35/1k grounding fee.

| Provider | Free Tier | Paid Price | Latency | Commercial-OK License | Notes |
|---|---|---|---|---|---|
| **Brave Search API** | $5 credit/mo (~1,000 queries) | $5/1k requests | ~300ms | Yes, commercial allowed | Independent index, privacy-respecting. Free tier shrunk in 2026 |
| **Tavily** | 1,000 credits/mo, no card | $0.008/credit pay-as-you-go; $30/mo Researcher | ~600ms | Yes | Designed for AI-grounding; clean JSON, citations included |
| **Serper** | 2,500 searches/mo | $50/yr (50k) → $0.001/search; $50/mo (500k) | ~200ms | Yes | Cheapest at scale; Google-results-as-API |
| **SerpAPI** | 100 searches/mo | $75/mo (5k) → $15/1k | ~400ms | Yes | Multi-engine; expensive |
| **Bing Search API** | — | **RETIRED Aug 11, 2025** | — | — | Migrate to Azure AI Foundry Grounding (not API-compatible) |
| **DuckDuckGo HTML scrape** | unlimited (rate-limited) | $0 | ~1s | Gray area; ToS prohibits scraping | Free but unreliable at >1 req/s. Skip for production |
| **You.com Search API** | limited beta | ~$5/1k | ~500ms | Yes | Smaller index than Brave |
| **Exa.ai** | 1,000 credits free | $5/1k queries (semantic) | ~700ms | Yes | Best for semantic/research-paper search; not great for breaking news |
| **Perplexity Sonar API** | — | Sonar Small: $0.20/$0.20 per 1M + $5/1k req; Sonar Pro: $3/$15 + $6–14/1k req | ~1.5–3s | Yes, but check terms for redistribution | All-in-one — model + grounding. Bypasses our local Gemma if we want a fully-managed answer |
| **Common Crawl** | Free dump (~3 PB total) | Compute only (~$50 to process a slice on Spot) | minutes (batch) | CC0 | Use for pretraining/eval, not online grounding |
| **Firecrawl** | 500 one-time API credits | Hobby $16/mo (3k credits); Standard $83/mo (100k); pay-as-you-go available | ~1–2s | Yes | Already configured (`FIRECRAWL_API_KEY`); does scrape AND search; `/extract` is separate token-billed |

**Recommended 2-stack architecture for the 5090:**

1. **Primary: Tavily free tier (1,000 queries/mo)** for AI-style grounded search with citations.
2. **Fallback: Firecrawl Hobby ($16/mo, 3,000 credits)** for scrape + structured extract on the URLs Tavily returns. Already wired.
3. **Overflow: Brave $5/1k pay-as-you-go** for any month we burst past Tavily's 1,000.

**Monthly budget at our hackathon scale:**
- 1k searches/day = 30k/mo: $16 Firecrawl + $145 Tavily = **~$160/mo** (or $150 Brave alone). Or stay on Gemini Pro grounding free tier if 1,500/day is enough = **$0**.
- 10k/day = 300k/mo: Serper Pro at $50/mo for 500k searches **wins decisively**.
- Demo-scale (≤100 searches/day): all-free combination of Tavily free tier + Brave $5 monthly credit + Gemini Pro 1,500/day free.

---

## 6. HuggingFace Plans & Credits — Go-Deep

### Pro Plan ($9/month, single most ROI-positive subscription on this list)

- **2M Inference Provider credits/month** (20× free tier). At Gemma 3 27B prices via DeepInfra-routing, that's roughly 2–10M tokens of usable compute — covers all of Mercury's cloud-burst budget.
- **8× ZeroGPU quota — up to 25 minutes/day of H200** (yes, H200, not H100) on Spaces with priority queue. **This is the public-Cortex-demo plan**. An H200 runs TRIBE v2 inference faster than the 5090, free, for 25 min/day.
- **10 ZeroGPU Spaces with Dev Mode** (SSH/VS Code) — we can stand up the Cortex demo Space and the Mercury chat Space, both ZeroGPU.
- **1TB private + 10TB public storage** — fMRI volumes fit here; Cortex weights fit; no extra storage bill.
- **Private dataset viewer**, blog publishing on profile, ticket support.

### Enterprise Hub (~$20/seat/month, 5-seat min)

- SSO, audit logs, SOC2, regions. **Skip until ISU IT requires it** — not worth the $100/mo floor for our team size.

### Inference Endpoints (managed, dedicated GPU)

- L4: **$0.80/hr** (~$580/mo always-on)
- A10G: **$1.00/hr** (~$720/mo)
- A100-80: **$2.50/hr** (~$1,800/mo) — can scale to 8x for $20/hr
- Billed by the minute. **No scale-to-zero by default** — Modal beats this for bursty workloads.

### Spaces (free CPU + paid GPU)

- Free CPU 16GB, $0
- Nvidia T4: $0.40/hr; A10G Small: $1.00/hr; A100: $4.00/hr (paid Spaces are *more expensive* than Inference Endpoints — don't use paid Spaces, use ZeroGPU under Pro instead)

### AutoTrain

- Per-job pricing, depends on hardware. Pro users get a discount and credits roll into the 2M/mo pool. **Not relevant for ABM × ISU** unless we fine-tune.

### ChatUI

- Open-source, free to self-host. Could be the public Mercury web surface if we don't want Cloudflare Workers.

### Programs ABM × ISU could legitimately apply for

| Program | What | How to apply |
|---|---|---|
| **Community GPU Grant** | Free A10G/A100 on a specific Space for a defined period | Open a discussion in your Space's `Settings → Hardware → Apply for a community grant`. Cite ABM × ISU research collaboration |
| **Academic Project Grant** | Same mechanism, flagged "Academic project" | Same flow; ISU affiliation is the qualifier |
| **NAIRR Pilot — HuggingFace track** | 100 compute grants HF contributes to NAIRR Pilot for academic research | Apply through https://nairrpilot.org with ISU PI co-signing |
| **Hugging Fellows** | Long-term researcher fellowships | Selective; not realistic this cycle but worth tracking |
| **TPU Research Cloud** (via Google, not HF) | Free TPU v5e credits for academic research | Apply through Google's TRC program — separate from HF but academic-friendly |

**Concrete recommendation:** **Subscribe to HF Pro this week**. The ZeroGPU H200 minutes alone replace the entire "public demo" budget line in the GCP plan ($5/user/month at 100 users → $500/mo) at $9/mo flat. **Apply for a Community Academic Project grant** the same day you push the public Cortex Space; ABM × ISU is exactly the profile they fund.

**Do NOT** use paid GPU Spaces — they are mispriced vs. Inference Endpoints. **Do NOT** subscribe to Enterprise Hub yet.

---

## 7. Non-GCP Hosting + Storage Alternatives

### Object Storage (fMRI uploads, Cortex datasets)

| Provider | Storage $/GB/mo | Egress | Free Tier | Integration | Notes |
|---|---|---|---|---|---|
| **Cloudflare R2** | $0.015 | **$0** | 10 GB | ★★★★★ — S3 SDK works | Class A ops $4.50/M, Class B $0.36/M. **The default choice** |
| **Cloudflare R2 IA** | $0.010 | $0 | — | ★★★★★ | $0.01/GB retrieval; for cold fMRI archive |
| **Backblaze B2** | $0.006 | $0.01/GB ($0 via Cloudflare Bandwidth Alliance) | 10 GB | ★★★★★ — S3 SDK | Cheapest *if* egressing through Cloudflare |
| **Wasabi** | $0.0069 | conditional/free with 1TB min commit | — | ★★★★ | 90-day min storage duration, 1TB min — overkill for us |
| **GCS** | $0.020 | ~$0.12/GB | 5 GB | ★★★★★ | Reference; ABM hates the egress |

**Pick: Cloudflare R2 standard.** At 100GB fMRI data, $1.50/mo. At 1TB, $15/mo. Egress to anywhere — including the 5090 — is free.

### Web Hosting (Mercury web surface, redteamkitchen.com)

| Provider | Free Tier | Paid Floor | Scale-to-Zero | GPU? | Integration |
|---|---|---|---|---|---|
| **Cloudflare Pages** | unlimited static, 500 builds/mo, 100k/day Workers reqs | $5/mo Workers Paid | yes | no | ★★★★★ |
| **Cloudflare Workers + DO** | 100k req/day | $5/mo + usage | yes | no | ★★★★★ — Mercury web could be a Worker |
| **Vercel** | hobby (commercial use restricted) | $20/mo Pro | yes | no | ★★★★ — not free for revenue-bearing use |
| **Fly.io** | none (small free trial) | $1.94/mo per 256MB shared CPU instance | yes (auto-stop) | **Deprecated post-Aug 2025** | ★★★★ — GPU SKU is gone |
| **Render** | free static, 750 hr/mo CPU | $7/mo per service | yes (paid) | no | ★★★ |
| **Railway** | $5 trial credits | usage-based, ~$5/mo floor | yes | no | ★★★ |
| **DigitalOcean Apps** | none | $5/mo Basic | no | no | ★★ |

**Pick: Cloudflare Pages for the public site, Workers for any API surface, all under the existing Cloudflare account.**

### GPU Compute (when 5090 is busy or down)

| Provider | A100-80 $/hr | H100 $/hr | Scale-to-Zero | Use Case | Stars |
|---|---|---|---|---|---|
| **Modal** | $2.50 | $3.95 | yes (per-second) | Cloud-Run-for-GPUs alternative — best for Cortex inference burst | ★★★★★ |
| **RunPod Serverless** | $2.31–2.72 | $3.55–4.18 | yes | Same use case, more cold-start | ★★★★ |
| **RunPod Community Cloud** | $0.89 | $2.39–2.69 | no (rented hour) | Cheap per-hour rentals for training | ★★★★ |
| **Lambda Labs** | $1.29 | $2.49–2.89 | no | Cheapest reserved long jobs | ★★★★ |
| **CoreWeave** | ~$2.20 | ~$3.50 | no | Enterprise — overkill for us | ★★ |
| **Vast.ai** | $0.52–0.67 | varies | no | Cheapest, peer-rented, ~50% of hyperscaler. **Reliability tax** — fine for batch eval, not for production demos | ★★★ |
| **Salad** | — (consumer GPUs only) | — | yes (per-sec) | Cheapest RTX 4090 ($0.16/hr); consumer-GPU only | ★★ |
| **TensorDock** | similar to RunPod | similar | yes | Smaller competitor | ★★★ |
| **Hugging Face Inference Endpoints** | $2.50 | not standard | per-minute | If we standardize on HF | ★★★★ |
| **Hugging Face ZeroGPU (Pro)** | H200, free under Pro | — | yes | **Public demo Space — best for hackathon** | ★★★★★ |

**Pick: HF ZeroGPU for the public demo Space. Modal for any private serverless burst. Vast.ai only for offline TRIBE v2 training jobs where reliability is acceptable.**

---

## 8. Mercury's Internal Provider Plumbing — What's Already Wired

Mercury already routes through `agent/auxiliary_client.py`, which is more sophisticated than the GCP plan accounted for. The auto-resolution chain (text tasks):

1. **OpenRouter** (`OPENROUTER_API_KEY`) — primary; aggregates DeepInfra/Together/Fireworks for Gemma SKUs
2. **Nous Portal** — Mercury 4 405B / Kimi K2.6, OAuth-authed
3. **Custom OpenAI-compat endpoint** (`OPENAI_BASE_URL` + `OPENAI_API_KEY`) — **this is how Ollama on the 5090 plugs in**
4. **Codex OAuth** (gpt-5.3-codex via chatgpt.com) — already wraps Responses API
5. **Native Anthropic** (`ANTHROPIC_API_KEY`)
6. Direct API-key providers: **Gemini, z.ai/GLM, Kimi/Moonshot, MiniMax, MiniMax-CN, HuggingFace, NVIDIA NIM, Xiaomi MiMo, Arcee, Ollama Cloud, KiloCode, Vercel AI Gateway**

Vision/multimodal chain prepends the user's selected main provider if it supports vision, then OpenRouter, Nous, Codex, Anthropic, custom.

Already-supported features:

- **Streaming** — yes, all OpenAI-compatible providers + native Anthropic + Gemini-via-OpenAI-compatible endpoint
- **Function/tool calling** — yes
- **402/credit-exhaustion fallback** — automatic; if OpenRouter runs out of credit Mercury falls through to Codex / Anthropic / next provider
- **Per-task overrides** — `auxiliary.vision.provider`, `auxiliary.compression.model`, `auxiliary.session_search.model` (config.yaml)
- **Provider routing on OpenRouter** — sort by price/throughput/latency; provider allowlist/blocklist; data_collection deny

What is **one-config swap** vs **needs code**:

- **One config swap (no code):** Switch primary to Gemini, OpenRouter, Anthropic, Nous, Ollama-Cloud, Ollama-local, GLM, Kimi, MiniMax, HF Inference, NVIDIA NIM. All via `~/.mercury/config.yaml model.provider: <name>` + corresponding env var.
- **Already plumbed through `gemini_native_adapter.py`**: native Gemini API (Vertex-style), supports Gemini 2.5/3.x, grounding, multimodal.
- **Code work needed:**
  - Direct **Vertex AI Model Garden Gemma endpoint** (uses gRPC, not OpenAI-wire) — would need a new transport
  - **Cerebras** dedicated SKU (uses non-OpenAI-wire SDK)
  - **Bedrock-routed Anthropic** (uses boto3, separate path — `bedrock_converse` exists but has its own timeout config)

Translation: every provider in this memo except Vertex Model Garden is reachable today by editing a YAML file.

---

## 9. Recommended Low-Cost Stack — Hackathon Submission

### Stack A: Demo + invited testers (now → next 30 days)

| Component | Recommendation | Monthly Cost |
|---|---|---|
| Cortex TRIBE v2 inference | RTX 5090 local (already paid) | $5–10 electricity |
| Mercury chat | Ollama Gemma 4 E4B on 5090 → fallback OpenRouter Gemma 4 26B A4B | $0–5 |
| Mercury reasoning (`/long`) | Ollama Gemma 4 26B-MoE on 5090 → fallback Gemini 2.5 Flash | $0–5 |
| Mercury multimodal | Ollama Gemma 4 E4B (text+vision) on 5090; 26B MoE for audio | $0–3 electricity |
| Cortex narration | OpenRouter Gemma 4 26B A4B (4 personas × 10 scans/day) | ~$2 |
| Internet grounding | Tavily free tier (1k/mo) + Firecrawl Hobby ($16) + Brave $5 free credit | $16 |
| Public Cortex demo | **HuggingFace ZeroGPU Space (Pro)** | $9 (the Pro sub) |
| fMRI storage | Cloudflare R2, 100 GB | $1.50 |
| Public web (redteamkitchen.com) | Cloudflare Pages (free) | $0 |
| Discord bot gateway | Local Mercury via Cloudflare Tunnel (free) | $0 |
| Domain | redteamkitchen.com (already paid) | — |
| **TOTAL** | | **~$40–50/mo** |

### Stack B: Always-on, public-facing, ~unlimited tokens

| Component | Recommendation | Monthly Cost |
|---|---|---|
| Cortex TRIBE v2 inference | **ACCESS-CI EXPLORE** allocation (free) → MAXIMIZE (free, awarded Oct 1) | $0 (academic compute) |
| Burst overflow when ACCESS-CI is queued | Modal serverless A100-80 ($2.50/hr × ~30hr/mo) | $75 |
| Mercury chat | OpenRouter Gemma 4 26B A4B at scale (~50M tokens/mo) | $20 |
| Mercury multimodal | Gemini 2.5 Flash-Lite for image-heavy bursts | $30 |
| Cortex narration (1k scans/mo) | OpenRouter Gemma 4 26B A4B | $80 |
| Grounding | Serper Pro ($50/mo, 500k searches) | $50 |
| Public demo | HF Pro + Community Academic Grant on the Space (free GPU) | $9 |
| fMRI storage | Cloudflare R2, 1 TB | $15 |
| Web | Cloudflare Workers Paid | $5 |
| **TOTAL** | | **~$285/mo** |

For comparison, the original GCP plan was $5/user/mo × 100 users = **$500/mo**, plus egress and Vertex management fees that drove the real number to ~$700–800/mo. Stack B at ~$285/mo serves the same load with HPC headroom and academic-license-clean data flow.

---

## 10. Action Items — This Week

Ordered by ROI (cheapest, biggest impact first):

1. **Subscribe to HuggingFace Pro — $9, 5 minutes.**
   Unlocks 25 min/day H200 ZeroGPU, 2M monthly inference credits, 1TB private storage, 10 Dev-Mode ZeroGPU Spaces. Replaces the Cloud Run public-demo line item entirely. **Why this is #1:** every other line item in the budget shrinks once we have ZeroGPU H200s available.

2. **Apply for an ACCESS-CI EXPLORE allocation — $0, ~30 minutes (one-page abstract).**
   Decided in days, not months. Even if we don't use the credits, the ACCESS-CI ID is the prerequisite for the larger MAXIMIZE allocation (June 15–July 31 submission window for Oct 1 award). Citation-able in any grant application.

3. **Move Mercury default provider to OpenRouter Gemma 4 26B A4B in `~/.mercury/config.yaml` — $0, 2 minutes.**
   No code change. Set `model.default: google/gemma-4-26b-a4b-it` and `model.provider: openrouter`. The 5090 stays the primary inference engine via the custom-endpoint chain; OpenRouter handles overflow and fallback. Auto-detects from `OPENROUTER_API_KEY`.

4. **Provision Cloudflare R2 bucket for fMRI uploads — $0 (10GB free), ~10 minutes.**
   Single `wrangler r2 bucket create cortex-fmri` and an S3-compatible signed-URL flow. Egress is free, including back to the 5090.

5. **Stand up the public Cortex demo as a HuggingFace ZeroGPU Space — $0 with Pro, ~half a day.**
   This is the hackathon submission's hero artifact. Open the Space, then immediately apply for a Community Academic Project GPU grant — the application form is in the Space settings.

6. **Switch internet grounding to Tavily-free + Firecrawl-Hobby — $16, ~30 minutes.**
   Already have Firecrawl key. Add `TAVILY_API_KEY` to `.env`, wire a single `web_search` tool that tries Tavily first, falls back to Firecrawl `/search`. Don't sign up for a Brave paid plan yet — the $5 monthly credit is enough.

7. **Disable any always-on Vertex AI / Cloud Run resources still running from the GCP plan — $0, 15 minutes.**
   `gcloud run services list` and `gcloud ai endpoints list`. Anything serving prediction traffic at idle is bleeding $50–200/mo. Confirm with `gcloud billing`.

8. **Set up Cloudflare Tunnel for the local Mercury Discord gateway — $0, ~30 minutes.**
   Avoids hosting a public Discord bot; the tunnel terminates inside the trust boundary. `cloudflared tunnel create mercury-bot`.

9. **Bookmark the NAIRR Pilot HuggingFace track ($0, 5 minutes) and the TRC TPU program for a future application.** These are 30-minute applications that take 4–6 weeks; line them up now so they land before the next semester's grant deadlines.

10. **Add a single `metrics_collector` line in `agent/auxiliary_client.py` to emit per-request token + provider — $0, ~1 hour.** We're flying blind on actual provider mix today. Without telemetry we can't make the next round of cost decisions.

---

## Sources

- [Gemini Developer API pricing | ai.google.dev](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini 3 Flash blog — pricing & global availability](https://blog.google/products-and-platforms/products/gemini/gemini-3-flash/)
- [Gemini 3.1 Pro Preview pricing | pricepertoken.com](https://pricepertoken.com/pricing-page/model/google-gemini-3.1-pro-preview)
- [Gemini API Pricing 2026 Complete Guide | MetaCTO](https://www.metacto.com/blogs/the-true-cost-of-google-gemini-a-guide-to-api-pricing-and-integration)
- [Gemini API Pricing & Calculator (Apr 2026) | costgoat.com](https://costgoat.com/pricing/gemini-api)
- [Grounding with Google Search | ai.google.dev](https://ai.google.dev/gemini-api/docs/google-search)
- [Gemini context caching — costs and 90% discount tier | aifreeapi.com](https://www.aifreeapi.com/en/posts/gemini-api-context-caching-reduce-cost)
- [Vertex AI Generative AI pricing | cloud.google.com](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [Gemma 4 26B A4B IT pricing | OpenRouter](https://openrouter.ai/google/gemma-4-26b-a4b-it)
- [Gemma 4 31B IT pricing | OpenRouter](https://openrouter.ai/google/gemma-4-31b-it)
- [Gemma 3 27B IT pricing | OpenRouter](https://openrouter.ai/google/gemma-3-27b-it)
- [DeepInfra Gemma 3 4B pricing | Inworld](https://inworld.ai/models/deepinfra-gemma-3-4b)
- [DeepInfra Gemma 3 27B pricing | LangDB](https://langdb.ai/app/models/gemma-3-27b-it)
- [Gemma 4 pricing $0.14/M comparison | TokenCost](https://tokencost.app/blog/gemma-4-pricing-benchmarks)
- [HuggingFace pricing | huggingface.co/pricing](https://huggingface.co/pricing)
- [HuggingFace Inference Endpoints pricing](https://huggingface.co/docs/inference-endpoints/en/pricing)
- [HuggingFace Inference Providers pricing & billing](https://huggingface.co/docs/inference-providers/en/pricing)
- [HuggingFace Spaces ZeroGPU docs](https://huggingface.co/docs/hub/en/spaces-zerogpu)
- [Brave Search API pricing | api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/pricing)
- [Brave Search API drops free tier — implicator.ai](https://www.implicator.ai/brave-drops-free-search-api-tier-puts-all-developers-on-metered-billing/)
- [Tavily Credits & Pricing](https://docs.tavily.com/documentation/api-credits)
- [Tavily pricing page](https://www.tavily.com/pricing)
- [Serper pricing](https://serper.dev/)
- [SerpAPI pricing](https://serpapi.com/)
- [Exa API pricing](https://exa.ai/pricing)
- [Perplexity Sonar API pricing](https://docs.perplexity.ai/docs/getting-started/pricing)
- [Firecrawl pricing](https://www.firecrawl.dev/pricing)
- [Bing Search API retirement & alternatives — searchcans.com](https://www.searchcans.com/blog/bing-search-api-retirement-alternatives-2026/)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [Cloudflare Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/)
- [Backblaze B2 vs Wasabi comparison](https://www.backblaze.com/cloud-storage/comparison/backblaze-vs-wasabi)
- [Fly.io pricing & GPU pricing/deprecation](https://fly.io/docs/about/pricing/)
- [Modal pricing](https://modal.com/pricing)
- [RunPod pricing](https://www.runpod.io/pricing)
- [Lambda Labs pricing](https://lambda.ai/pricing)
- [Salad Cloud pricing | salad.com](https://blog.salad.com/lowest-cost-gpus/)
- [Vast.ai vs RunPod 2026 comparison](https://medium.com/@velinxs/vast-ai-vs-runpod-pricing-in-2026-which-gpu-cloud-is-cheaper-bd4104aa591b)
- [Groq pricing](https://groq.com/pricing)
- [ACCESS-CI for researchers](https://access-ci.org/get-started/for-researchers/)
- [ACCESS-CI Allocations Policy](https://allocations.access-ci.org/allocations-policy)
- [NAIRR Pilot — National Science Foundation](https://www.nsf.gov/focus-areas/ai/nairr)
- [HuggingFace community grant flow — example Space discussion](https://huggingface.co/spaces/OpenGVLab/ScaleCUA-Grounding/discussions/1)
- [RTX 5090 power consumption — overclocking.com](https://en.overclocking.com/review-nvidia-rtx-5090-founders-edition/12/)
