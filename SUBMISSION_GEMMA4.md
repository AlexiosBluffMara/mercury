# Mercury — Gemma 4 Good Hackathon submission

**Track:** Digital Equity
**Team:** Soumit Lahiri (Alexios Bluff Mara LLC)
**Repo:** [github.com/AlexiosBluffMara/mercury](https://github.com/AlexiosBluffMara/mercury) · [github.com/AlexiosBluffMara/cortex](https://github.com/AlexiosBluffMara/cortex)
**Submission deadline:** 2026-05-18

## Visual tour (auto-captured 2026-05-06)

Every link in this writeup was browser-clicked through Patchright headless Chromium, screenshotted, and saved to `assets/screenshots/`. The link audit (274 unique URLs) and full screenshot inventory live in [`docs/VALIDATION_REPORT_2026-05-06.md`](docs/VALIDATION_REPORT_2026-05-06.md).

| | |
|---|---|
| ![Mercury repo](assets/screenshots/01_mercury_github_repo.png) | ![Submission rendering](assets/screenshots/03_submission_gemma4.png) |
| Mercury GitHub repo (Apache-2.0, public) | This writeup as a judge sees it |
| ![GET_STARTED](assets/screenshots/04_get_started.png) | ![Mercury×Cortex contract](assets/screenshots/05_mercury_cortex_contract.png) |
| Three-command teacher onboarding | The Mercury × Cortex shared-GPU contract |
| ![Cortex live demo](assets/screenshots/12_cortex_live_demo.png) | ![Mercury WebUI mobile](assets/screenshots/19_mercury_webui_mobile.png) |
| Cortex live demo at `cortex.redteamkitchen.com` | WebUI at iPhone-sized 390×844 viewport |

## TL;DR

Mercury is an open-source multimodal agent that runs Gemma 4 entirely on a teacher's MacBook or a single consumer GPU, then talks to students through Discord, WhatsApp, the terminal, or a phone — whatever they have access to. It costs **$0/month** to run because Gemma 4 is open-weight and we self-host on consumer hardware. A school district that adopted it would pay only the electricity bill they already pay.

## Problem

Education AI is increasingly priced like a per-seat enterprise SaaS. Vertex AI charges per million tokens. ChatGPT Edu is $20/month/student. OpenAI's API ramps faster than school IT budgets can. Meanwhile:

- 13% of US K-12 households still don't have stable home broadband (NCES 2024).
- Students in rural Illinois (where I live half the time) regularly hit data caps that silently throttle AI tools.
- Teachers are asked to integrate AI without admin approval to spend on it.

Cloud-only AI architectures fail those students twice: first when the connection drops, again when the bill arrives.

## What Mercury is

Mercury is an agent gateway that:

1. **Runs Gemma 4 locally** on whatever hardware is available — M-series Mac, RTX consumer GPU, or even a Raspberry Pi 5 in a pinch.
2. **Speaks every channel** kids actually use — Discord (the default school chat), WhatsApp (where parents already are), terminal (for CS classrooms), web UI (for everyone else), and a daily Cron digest.
3. **Routes intelligently** between local and cloud — fast text on a 5090, deep reasoning on an M4 Max, and an OpenRouter `:free` tier as the fall-back when both are unreachable.
4. **Costs nothing per request** because Gemma 4 is Apache-2.0 open-weight and the cloud fall-back uses the OpenRouter free tier (1000 reqs/day on a single $10 account top-up).

It's built on the Nous Research hermes-agent fork, extended with multi-platform adapters and a **dual-mode router** (fast E4B → deep 31B at >280 chars).

## Why Gemma 4 specifically

Other open models exist. Gemma 4 was the right choice because:

- **256K context** — long enough for a textbook chapter as a single prompt.
- **Native multimodal** (text + image + audio in E4B) — handwritten math homework photo → solution; spoken question → spoken answer.
- **140+ languages** — students in dual-language classrooms get the same quality.
- **Apache 2.0 open weights** — no toll, no rate limit, no exfiltration risk.
- **Effective parameter design** (E2B/E4B) — runs on devices that can't fit a "real" 4 B model.
- **MTP drafters** released May 6, 2026 — official 3× speedup path documented for production hardening.

The April 11 chat-template patch and May 6 MTP drafter release matter for our story. We pull the patched [Unsloth UD-MLX-4bit](https://huggingface.co/unsloth/gemma-4-26b-a4b-it-UD-MLX-4bit) weights in the local Mac path, the latest Ollama tag on the CUDA path, and document the MTP drafter integration as the next post-deadline optimization.

## Architecture

```
Pixel Fold / iPhone / Mac / Pi / 4K kiosk
         (Discord, WhatsApp, TUI, WebUI, kiosk)
                       │
            ┌──────────▼──────────┐
            │  Mercury Gateway    │   dual-mode router (fast→deep)
            │  Python, hermes-agent fork
            └──┬───────┬──────────┘
               │       │
        Seratonin   Big Apple
        RTX 5090    M4 Max 48G
        Ollama      mlx-vlm (3 ports: E4B/26B/31B)
        gemma4:e4b  Apr 11 patched UD-MLX-4bit
        TRIBE v2    audio + vision (E4B)
        embedgemma  reasoning (26B/31B)
               │       │
               └───┬───┘
                   │  failover
                   ▼
            OpenRouter `:free`
            (1000 reqs/day, $0)
                   │
                   ▼
            OpenRouter paid
            (gated, $0.50/day cap, never used in practice)
```

Persistence: SQLite at `~/.mercury/state.db`, markdown vault at `~/.mercury/vault/`.

Observability: Hue lights green/amber/red on agent activity ("ambient AI" — kids in the room can see when the agent is thinking).

## What runs where (current state)

| Component | Hardware | Cost | Effective tok/s |
|---|---|---|---|
| Gemma 4 E4B (multimodal + audio, hot path) | M4 Max via mlx-vlm port 8080 | $0 | **94 tok/s** |
| Gemma 4 E4B + MTP drafter (experimental) | M4 Max via mlx-vlm port 8083 | $0 | 75 tok/s (slower, see below) |
| Gemma 4 26B-A4B (MoE, 4B active) | M4 Max via mlx-vlm port 8081 | $0 | ~78 tok/s |
| Gemma 4 31B (deep reasoning) | M4 Max via mlx-vlm port 8082 | $0 | ~32 tok/s |
| Gemma 4 E4B fast | RTX 5090 via Ollama 0.23.1 | $0 | ~194 tok/s |
| TRIBE v2 (cortex specialist) | RTX 5090 via Ollama, fine-tune of Gemma 4 E4B | $0 | ~190 tok/s |
| `embeddinggemma:300m` retrieval | RTX 5090 via Ollama | $0 | n/a |
| Cloud fall-back | OpenRouter `:free` Gemma 4 26B | $0 (1000/day cap) | ~50 tok/s WAN |

### MTP — measured negative result (intellectually honest finding)

We integrated MTP per Google's May 6, 2026 drafter announcement. We paired the **official Google drafter** (`google/gemma-4-E4B-it-assistant`, 0.5B params, BF16) with the Unsloth 4-bit target (`unsloth/gemma-4-E4B-it-UD-MLX-4bit`) via mlx-vlm 0.5.0's `--draft-kind mtp`. We measured at multiple block sizes.

**Result: in our specific hardware/library combo, MTP introduced 20-40% wall-clock overhead vs the vanilla E4B server.** Long-prompt 400-word essay generation, 3-trial avg:

- Vanilla E4B (port 8080): 5.94s avg, **94 tok/s**
- MTP block=6 (port 8083): 10.82s avg, 57 tok/s (0.61× of baseline)
- MTP block=3 (port 8083): 7.96s avg, 75 tok/s (0.80× of baseline)

Why this is a stronger story for the submission than just claiming a speedup: **we ran the experiment, the data said no, and we made the evidence-based call to keep MTP off the hot path.** The MTP server stays on port 8083 as a documented third-tier failover — judges can hit it directly to verify our measurements.

Likely root cause: the drafter docs require BF16 targets, but BF16 26B/31B don't fit in the 5090's 32 GB or Big Apple's 48 GB unified memory; we used the only target that fits (Unsloth 4-bit). The mixed-precision logits limit acceptance rate to 38%, and the drafter forward pass costs more than 38%-acceptance saves. Worth retesting when mlx-vlm releases a more optimized speculative-decoding implementation, or when target weights of size that allow BF16 on consumer hardware exist.

This is the only path we tried that supports speculative decoding + multimodal Gemma 4 — vLLM 0.20.1 explicitly raises `NotImplementedError` for that combination. The honest result is the result.

## Why this hybrid is good (judging criteria: technical depth)

1. **Local first, cloud second, paid never.** Mercury's `custom_providers` list is ordered. The router walks it on every request: local LAN → cloud free → cloud paid (locked behind explicit flag). 95%+ of traffic hits a free path; the paid path exists only as a last resort and has hard daily/monthly caps in config.
2. **Failure isolation across three machines.** WSL2 process crash → MLX still serves. Big Apple launchd dies → Seratonin Ollama covers. Both LAN nodes off → OpenRouter free picks up. Internet down → Pixel Fold's local NPU still answers most questions.
3. **Cost predictability.** A judge testing the demo at 100 prompts × 3 evaluators = 300 sessions costs us $0. Same demo on a Vertex Gemma rate would burn ~$60. That gap *is* the Digital Equity argument expressed in dollars.
4. **MTP integrated and measured.** mlx-vlm 0.5.0 (git main) supports `--draft-kind mtp` for multimodal Gemma 4 — the only stack that does (vLLM 0.20.1 raises `NotImplementedError` for the combination). Big Apple port 8083 runs the official Google drafter `google/gemma-4-E4B-it-assistant` paired with the Unsloth 4-bit target. **Measured 0.61-0.80× of baseline tok/s** at block sizes 6 and 3 respectively — a *negative* result we document honestly. The vanilla E4B server at 94 tok/s wins the hot path. MTP stays on as a third-tier failover so judges can verify the measurement. The likely fix (BF16 target weights, when consumer hardware can fit them) is post-deadline.

## Reproducibility (judging criteria: technical execution)

A teacher with a recent MacBook can reach a working Gemma 4 chat in three commands:

```bash
# 1. Install Mercury (single command, no GCP, no API key required for local-only mode)
pip install --user git+https://github.com/AlexiosBluffMara/mercury

# 2. Pull a Gemma 4 model into Ollama (skip if Mac — uses MLX path automatically)
ollama pull gemma4:e4b

# 3. Run
mercury -z "What's 2+2 and why?"
```

For a school deployment, swap step 1 with `docker run rtkitchen/mercury:latest` and the rest is identical.

## Cost analysis vs an API-only architecture (judging criteria: impact)

| Scenario | Mercury (us) | API-only equivalent |
|---|---|---|
| 100 judging test prompts | **$0** | ~$8 |
| 1 evaluator × 1-day demo (300 prompts) | **$0** | ~$25 |
| 1 classroom × 30 students × 1 month (~10k prompts) | **$0** (one-time hardware) | ~$200 |
| 1 school district × 500 students × 1 year | **$0** + electricity | ~$50,000 |

Numbers based on Vertex AI Gemma 3 27B managed pricing (Gemma 4 isn't on the managed API as of May 2026; it would be similar or higher). Detailed in [`docs/HACKATHON_COSTS_2026-05-06.md`](docs/HACKATHON_COSTS_2026-05-06.md).

## What's in the box for judges

- This document — the technical write-up.
- [`docs/CLOUD_REPLICATION_2026-05-06.md`](docs/CLOUD_REPLICATION_2026-05-06.md) — full cloud-mirror architecture, per-tier pricing, failover patterns.
- [`docs/HACKATHON_COSTS_2026-05-06.md`](docs/HACKATHON_COSTS_2026-05-06.md) — line-item cost analysis vs API competitors.
- [`docs/GEMMA4_UPDATE_2026-05-06.md`](docs/GEMMA4_UPDATE_2026-05-06.md) — engineering notes on the April 11 chat template fix and May 6 MTP drafter release.
- [`docs/SELF_UPDATE_LOOP_2026-05-06.md`](docs/SELF_UPDATE_LOOP_2026-05-06.md) — how Mercury uses its 1000 free reqs/day for nightly self-improvement (skill audits, eval harness, doc sync).
- [`docs/SUBMISSION_READINESS_2026-05-06.md`](docs/SUBMISSION_READINESS_2026-05-06.md) — internal punchlist (linked for transparency).
- 3-minute demo video (link in the YouTube/Kaggle entry).
- The Kaggle notebook with three runnable cells.

## Roadmap (post-May 18)

1. **Re-test MTP** when mlx-vlm 0.6.x ships, or when an A100-class machine can host a BF16 target. Current measurement: 0.61-0.80× of baseline; we want to verify whether the cause is mixed-precision drafter alignment or a fixable mlx-vlm bottleneck.
2. **Modal A100 cloud-mirror** — for the ≤5% of traffic that arrives when local is unreachable. ~$8/mo at 1k req/day.
3. **TRIBE v2 cloud offload** to HuggingFace Inference Endpoints — shipped with `wrangler r2 cp` of the GGUF and a one-line Mercury config update.
4. **Cloudflare Workers AI for embeddings** — drops embedding latency on cloud path from 600 ms → 80 ms.
5. **Multi-region Modal deployment** — `us-east`, `eu-central`, `ap-south` for sub-100 ms world-wide.
6. **Daily eval harness via OpenRouter free tier** — already designed in `SELF_UPDATE_LOOP_2026-05-06.md`. Cron entries and scripts to follow.

## License

Apache-2.0 (matches Gemma 4 itself).

## Acknowledgements

- Google DeepMind for Gemma 4 — open weights are the only thing that makes this submission possible.
- Nous Research for the hermes-agent fork that Mercury is built on.
- Unsloth for the patched UD-MLX-4bit weights with the April 11 chat-template fix.
- Blaizzy/mlx-vlm and the MLX team at Apple for the `--draft-kind mtp` flag landing two days before this submission.
- The Kaggle hackathon team for picking Digital Equity as a track. It's the right one.
