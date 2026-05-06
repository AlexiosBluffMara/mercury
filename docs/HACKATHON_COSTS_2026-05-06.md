# Google Gemma 4 Good Hackathon — Cost Assessment

**Updated:** 2026-05-06
**Submission deadline:** 2026-05-18
**Track:** Digital Equity (primary), with Health and Education as adjacent fits
**Prize pool:** $200,000 across general, impact, and technical categories
**Rules surface:** Public Kaggle code repo + working demo + technical write-up + short demo video

## Bottom line

**Our submission's marginal cost from now to deadline: ~$0** for inference.

Gemma 4 is open-weight (Apache 2.0), so all Mercury inference traffic that hits Big Apple MLX or Seratonin Ollama is unbilled — we pay only electricity. The only line items below the deadline are optional cloud paths we'd add for redundancy.

## Why this matches the Digital Equity track narrative

The hackathon explicitly emphasizes "classrooms with weak internet" and "offline-first use cases." Our entire stack already runs that way: Pixel Fold → Mercury Discord → Big Apple MLX (LAN) or Seratonin Ollama (LAN), no internet round-trip needed. That's the differentiator versus teams routing through Vertex/Gemini API.

The hackathon page also notes: *"the winners will not necessarily be the people with the most complicated architecture"* — judges reward practical impact. Local-first deployment running on a teacher's M-series Mac is exactly the kind of practical impact Digital Equity rewards.

## What Google charges for Gemma 4 inference

| Provider | Input $/M tokens | Output $/M tokens | Notes |
|----------|------------------|-------------------|-------|
| **Self-host (us)** | **$0** | **$0** | Big Apple MLX + Seratonin Ollama |
| Vertex AI | not yet listed | not yet listed | Gemma 4 isn't on the managed API as of May 2026 |
| Google AI Studio | free tier | free tier | Prototyping only; no SLA |
| OpenRouter (free) | $0 | $0 | `google/gemma-4-26b-a4b-it:free` (rate-limited) |
| OpenRouter (paid) | $0.06 | $0.33 | 26B-A4B paid tier |
| Together AI / Baseten | $0.15–0.60 (combined) | — | Hosted Gemma 4 |
| HuggingFace Inference Endpoints | hourly GPU + idle | — | $0.50–2.00/hr active, scales to zero |

**Key insight:** Because Gemma 4 is open-weight, there is **no managed Google API price for it** — Google rewards self-hosting by removing the toll booth. This is the opposite of Gemini, where every prompt is metered.

## Hackathon-specific cost levers

### Free resources I'm aware of
- **Kaggle Notebooks** — 30 hr/week free TPU, 30 hr/week free GPU (T4 / P100). Sufficient for fine-tuning runs and validation but **not** for serving. We're not using these because our local hardware is bigger.
- **Google AI Studio** — free tier for Gemma family. We could add it as a third fallback after local + OpenRouter, but it's redundant for our offline-first story.
- **OpenRouter free tier** — `google/gemma-4-26b-a4b-it:free`. Already wired into Mercury config as `cloud-free` alias for backstop.

### Optional spend before deadline
None planned. Items we explicitly **opted out of**:
- Vertex AI / Gemini API — purged 2026-05-01 after the $200 overspend incident; budget kill switch deployed.
- Cloud GPU rental for 31B serving — Big Apple's M4 Max + Seratonin's RTX 5090 cover everything we need at zero marginal cost.
- Hosted Gemma 4 inference (Together / Baseten) — would mostly duplicate what we already serve locally.

### Optional spend post-deadline (cloud offload roadmap)
The hackathon judging looks at practical scaling potential. Two follow-on offloads we're scoping:

1. **TRIBE v2 cloud offload** — currently `cortex-gemma-4-e4b:latest` on Seratonin Ollama. To make this reachable from the public web app for users without the Tailscale mesh, we'd push the GGUF to:
   - **HuggingFace Inference Endpoints** ($0.50–1.20/hr active, scales to zero) — lowest ops, native HF auth, recommended.
   - **Modal Labs** ($0.40–0.90/hr active, pay-per-second, deeper Python integration).
   - **Replicate** (cog-based packaging, $0.001/sec for L4-class GPU).
   - Avoiding Vertex AI Endpoints per the May 1 incident.

2. **31B / 26B cloud burst** — only triggered when both Big Apple and Seratonin are unreachable (rare). Would route to OpenRouter free first, paid OpenRouter second, then hosted Together AI as last resort.

**Estimated monthly cost for both, at 1k requests/day average:**
- TRIBE v2 on HF Endpoints, ~30s/request, scaled to zero between bursts: ~$8–15/month
- OpenRouter overflow (paid) hitting only ~5% of requests at 26B-A4B pricing: ~$3–5/month
- **Total post-deadline cloud overhead: under $20/month** if we ship both offloads

## What "Be Googley" looks like in this submission

Per the user-level instruction (`Be Googley`):
- Cross-device — Pixel Fold (Discord), Mac (WebUI), iPhone (Discord), 4K display (Cortex kiosk via Baby Pi).
- Native primitives — Pixel Desktop Mode, Quick Share for asset transfer, Material 3 in the WebUI, GA4 + GTM on the public site.
- Identity rooted at `soumitlahiri@philanthropytraders.com` for everything (Tailscale, Kaggle, GitHub, GCP).
- 10× thinking — by self-hosting we can answer the "what if 1k students hit it on a school WiFi?" question with "we already do that, the bottleneck is the WAP not the AI."
- No Vertex / Gemini API in the hot path — gated by the budget kill switch.

## Comparison vs an "API-only" team's spend

A team that built the same demo on Vertex AI Gemma would burn (assumed numbers since Gemma 4 isn't on Vertex yet, using Gemma 3 27B comparable rate):
- ~$0.20 per demo session (3-turn conversation with images) at managed-Gemma rates
- 100 judging-time test runs × 3 evaluators = 300 sessions = **~$60** before they even ship
- 1k user demo day = **~$200**
- That's *just to be evaluated*. Our equivalent: $0.

## Implications for technical write-up

The submission write-up should explicitly call out:
1. **Apache 2.0 + open weights = no toll** — judges should understand we made a deliberate cost choice, not just a technical one.
2. **All inference local-first** — runs on consumer hardware (M4 Max MacBook, RTX 5090 desktop, Pi 5 edge).
3. **MTP speculative decoding** integrated locally for 2–3× speedup on 31B (vLLM on RTX 5090, mlx-vlm on M4 Max) — quality identical, throughput tripled, **still zero marginal cost**.
4. **TRIBE v2 specialist** — fine-tuned cortex model on Seratonin shows we can ship custom variants without paying per-token fees.
5. **Sub-$20/month cloud burst path** — practical scaling story without going over a teacher's school district AI budget.

## Sources

- [Gemma 4 Good Hackathon — Kaggle](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
- [EdTech Innovation Hub coverage](https://www.edtechinnovationhub.com/news/kaggle-and-google-deepmind-open-gemma-4-hackathon-focused-on-ai-skills-and-real-world-impact)
- [AI Cost Check — Gemma 4 self-host vs API](https://aicostcheck.com/blog/google-gemma-4-cost-analysis-open-model-2026)
- [TokenCost — Gemma 4 pricing benchmarks](https://tokencost.app/blog/gemma-4-pricing-benchmarks)
- [Vertex AI Gen-AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [OpenRouter Gemma 4 26B-A4B](https://openrouter.ai/google/gemma-4-26b-a4b-it)
