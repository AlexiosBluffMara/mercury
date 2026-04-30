<p align="center">
  <img src="assets/banner.svg" alt="Mercury — local-first dual-brain agent" width="100%">
</p>

# Mercury

> **Fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) (MIT) by [Red Team Kitchen](https://github.com/AlexiosBluffMara).**
> Submitted to the **Nous Research + Kimi Hackathon — Creative category** (due May 3, 2026).

**Built with Kimi K2.6 (hackathon sprint) · Now running Gemma 4 E4B (production)**

## What it is

Mercury is a personal AI assistant. It runs on your own computer.

You talk to it from any of six places — your terminal, Discord, a web page, iMessage, email, your phone — and the same agent answers, with the same memory, on the same hardware. No round-trips to anyone else's cloud.

It comes with four specialist skill sets out of the box:

- **Chicago college search** — eight public + five private universities, MBA modalities, ROI analysis.
- **Chicago tax & tenant law** — Cook County property taxes, the Residential Landlord and Tenant Ordinance, courts, legal aid.
- **3D web graphics development** — React Three Fiber, GLSL shaders, Blender, WebXR.
- **Hackathon submission packaging** — the skill that built this README.

The original hackathon sprint ran on **Kimi K2.6**, an open-weight model from Moonshot AI accessed through the Nous Portal — 14 commits, 75 minutes, $22.04. The live agent now runs on **Gemma 4 E4B** locally at 194 tok/s on an RTX 5090 via Ollama — zero API cost, zero cloud dependency. The body is **Hermes Agent**, an open-source framework from Nous Research. Mercury is what we built on top — a multi-domain stack you can fork and bend to your own four problems.

To run it on your hardware, jump to [Try it yourself](#try-it-yourself).

---

## Architecture

<p align="center">
  <img src="assets/architecture_v2.png" alt="Mercury — Hermes Multi-Domain Agent Stack" width="100%">
</p>

Six client surfaces fan into a single Hermes Gateway. The gateway routes through a Nous Portal brain (Kimi K2.6 inference), a tool router, a context-aware skill dispatcher, and a cross-session memory store. Four custom skill domains (Chicago Education, Chicago Tax/Legal, Three.js Design Dev, Nous Hackathon Packager) compose tools out of a five-source data layer. The whole stack runs across three nodes — a Mac Mini in Bloomington for skill authoring, a self-hosted RTX 5090 in Chicago for inference, and Google Cloud Run as managed fallback / scale.

| Custom skills (4 domains) | Multi-node infra | Hermes-native |
|---|---|---|
| **chicago-education** — 8 public + 5 private universities, MBA modalities, ROI analysis | **Mac Mini (M4 Pro, Bloomington)** — skill authoring, memory, dev | Auto-loading skills by domain context (no manual `/skill` needed) |
| **chicago-tax-legal** — Cook County property taxes, RLTO, courts, legal aid orgs | **Chicago 5090 (RTX 5090)** — GPU inference, heavy compute, self-hosted | Persistent cross-session memory (user profile + environment facts) |
| **threejs-design-dev** — R3F, GLSL shaders, Blender pipeline, WebXR, performance | **Google Cloud Run** — managed fallback, auto-scaling, public API endpoint | Subagent delegation for parallel research + code generation |
| **nous-hackathon** — demo scripts, deployment recipes, video storyboard | One-command `rsync` syncs skills + config across all nodes | Cron jobs + webhooks for scheduled monitoring tasks |

### Architecture v1 → v2 (what changed and why)

| Surface | v1 (deprecated) | v2 (current) |
|---|---|---|
| Brain | Hermes 4 405B + Kimi K2.6 split-role planner/coder | Single Kimi K2.6 brain via Nous Portal — simpler, cheaper, faster planning |
| Skill model | Three demo skills hard-coded into the agent loop | Skill Dispatcher auto-loads by domain context — 4 domains today, n+1 tomorrow without code change |
| Nodes | Single 5090 with manual ssh fallback | 3-node mesh: Mac Mini (dev) ↔ 5090 (inference) ↔ Cloud Run (scale), one-command sync |
| Clients | Discord-only | Six surfaces: Terminal, Discord, Web UI, iMessage, Email, Mobile |
| Memory | Per-session only | Cross-session profile + environment facts |
| Data layer | Filesystem only | Filesystem + Web Search + Browser MCP + Python Exec + Knowledge Graph |

The v1 diagram (preserved for reference) lives at [`assets/architecture_v1_deprecated.png`](assets/architecture_v1_deprecated.png). The v2 above is the current shipping topology.

---

## Initial Sprint by Kimi K2.6 (via Nous Portal) — Proof of Use

> **This section is part of the Nous Research / Kimi Track submission only. It does not appear in the Cortex / Gemma-4-Good Kaggle submission.**

<p align="center">
  <img src="kimi_proof/06_nous_portal_usage_2026-04-30.png" alt="Nous Portal usage — $22.04 spend, 1,035 requests, kimi-k2.6 spike Apr 28-29" width="100%">
</p>

**Verified Nous Portal spend, 7-day window 2026-04-23 → 2026-04-30:**

| Metric | Value |
|---|---:|
| Total spend | **$22.038114** |
| Requests | **1,035** |
| Input tokens | **57,080,009** |
| Output tokens | **564,754** |
| Cache reads | **39,529,312** |
| Cache writes | 0 |

Models hit on the account: `moonshotai/kimi-k2.6` *(the Apr 28-29 spike, ≈ $19.50)*, `moonshotai/kimi-k2`, `NousResearch/Hermes-4-405B`, plus a small non-inference line.

### What the $22 produced

The Kimi K2.6 spike on Apr 28-29 maps 1:1 to a 75-minute burst of 14 commits in this repo, all driven through `tools/kimi_dispatch.py` (Claude Code → Kimi K2.6 via Nous Portal):

| Time (CDT) | Commit | What Kimi wrote |
|---|---|---|
| Apr 28 08:45 | `982794c2` | `feat(skills): brain-viz creative skill + Kimi dispatch helper` |
| Apr 28 09:00:33 | `62a4edd3` | `feat(skills): fmri-overlay, tailnet, discord-bot for the Nous submission` |
| Apr 28 09:00:41 | `80038805` | `docs(nous): submission writeup for Nous Creative Hackathon` |
| Apr 28 09:05 | `cae58eaf` | `docs(nous): .env.example Mercury section + BENCHMARKS.md` |
| Apr 28 09:06 | `d810e6d7` | `chore(gitignore): ignore Kimi dispatch artifacts` |
| Apr 28 09:07 | `7a64cde1` | `fix(tools/kimi-dispatch): SSE streaming + 600s timeout` |
| Apr 28 09:08 | `684f674d` | `docs(skills/tailnet): Pixel 9 Pro Fold onboarding guide` |
| Apr 28 09:11 | `74e7bc18` | `fix(tools/kimi-dispatch): suppress thinking + fallback to reasoning` |
| Apr 28 09:18 | `585232e1` | `feat(skills/fmri-overlay): R3F implementation + dispatcher default flip` |
| Apr 28 09:44 | `ddc0ce83` | `feat(mercury-web): /cortex page wires fmri-overlay into the dashboard` |
| Apr 28 09:59 | `50423c0d` | **`feat(mercury-web/cortex): vanilla three.js viewer + Gemma narration panels`** |
| Apr 28 10:01 | `c8d0a36f` | `feat(cloudrun): mercury-web failover spec + bundle narration JSON` |
| Apr 29 17:21 | `8626b2be` | `docs(README): rewrite for hackathon submission — local Ollama + Academy personas` |
| Apr 29 18:10 | `bafa5fde` | `docs: add Academy hackathon submission section + Kimi K2.6 integration` |

The 09:59 commit is the actual cortex viewer (47 KB `main.js`, 36 KB `index.html`, 50-region atlas, brain mesh) running at `D:/cortex/webapp/public/` and visible in the demo video.

### Authorship artifacts (archived in this repo)

| Path | What it proves |
|---|---|
| `tools/kimi_dispatch.py` | The dispatcher — every Kimi call this account ever made flowed through here |
| `environments/tool_call_parsers/kimi_k2_parser.py` | Mercury's Kimi-specific tool-call parser, only present because Kimi was the integrated coder model |
| `kimi_proof/04_sessions_snapshot/` | 21 Mercury session/request-dump files containing raw POST bodies to `inference-api.nousresearch.com/v1/chat/completions` with `"model": "moonshotai/kimi-k2.6"` |
| `kimi_proof/05_config_with_kimi_default.yaml` | Mercury config in effect during the Kimi spike — `default: moonshotai/kimi-k2.6 / provider: nous-portal` |
| `kimi_proof/06_nous_portal_usage_2026-04-30.png` | The Nous Portal usage chart screenshot (image at top of this section) |
| `kimi_proof/07_kimi_spend_window_commits.txt` | Full `git log` of every commit in the Apr 27-30 window |

Reproduce the timeline yourself:
```bash
git log --all --pretty='%h | %ai | %s' --since='2026-04-27' --until='2026-04-30' .
```

---

## What Mercury Is

Mercury is a local-first autonomous agent running on an RTX 5090 desktop. It is the operational brain behind **[Cortex](https://github.com/AlexiosBluffMara/cortex)** — a multimodal brain-response analysis system that combines TRIBE v2 (Meta's brain foundation model) with Gemma 4 to predict and explain cortical activation in response to video, audio, or text stimuli.

The creative submission is Mercury acting as the orchestrator that drives the Cortex pipeline — accepting media inputs, routing them through TRIBE v2 inference, and generating multi-audience narrations of the brain's predicted response.

---

## Live Deployment

| | |
|---|---|
| **Discord** | Snowy The Bot, #bot-test-3 (invite-only) |
| **Model** | Gemma 4 E4B — RTX 5090, fully local |
| **Nous Portal / Kimi K2.6** | Used for hackathon sprint only |

---

## Current Model Config

- Default model: `gemma4:e4b` via Ollama at `localhost:11434`
- Runs on RTX 5090 (32 GB GDDR7)
- Provider config: `custom:ollama-local` in `~/.mercury/config.yaml`

---

## Models (RTX 5090 — local Ollama)

| Role | Model | Capability |
|---|---|---|
| Default / Vision / Multimodal | `gemma4:e4b` | completion · vision · audio · tools · thinking |
| Deep reasoning / long context | `gemma4-26b-moe:latest` | completion · tools · thinking |
| Fine-tuned cortex model (in training) | `cortex-gemma-4-e4b` | LoRA on TRIBE v2 narration turns |

All models run locally via Ollama at `http://localhost:11434`. No cloud API calls in the hot path.

```yaml
# ~/.mercury/config.yaml
model:
  provider: custom
  base_url: http://localhost:11434/v1
  api_key: ollama
  default: gemma4:e4b
  routing:
    vision: gemma4:e4b
    fast: gemma4:e4b
    deep: gemma4-26b-moe
    reasoning: gemma4-26b-moe
```

**Verified live:**
```
gemma4:e4b → "Mercury is live."  ✓
```

---

## Cortex — Creative Submission

**[Cortex](https://github.com/AlexiosBluffMara/cortex)** is a multimodal brain-response analysis system built on TRIBE v2 + Gemma 4:

- **TRIBE v2** (Meta) — predicts fsaverage5 BOLD responses at 20,484 vertices × 2 Hz from video, audio, or text
- **Gemma 4 E4B** — multimodal description + three-audience narration (General / College / Clinical) in parallel
- **Three.js viewer** — real-time per-vertex cortical activation animation with ISU cardinal colormap
- **GPU scheduler** — IDLE → GEMMA_ACTIVE → TRIBE_ACTIVE eviction-driven swap on 32 GB VRAM
- **LoRA fine-tune** — Gemma 4 E4B training on TRIBE v2 narration turns for domain specialization

Mercury drives the Cortex scan endpoint, routes media through the TRIBE v2 pipeline, and serves as the orchestrator for the hackathon demo.

### Kimi Track — Claude→Kimi Orchestration

Mercury also served as the **Kimi dispatch layer** for the hackathon's Kimi Track:

- Mercury dispatched specs (written by Claude Code) to **Kimi K2.6** via `tools/kimi_dispatch.py`
- Kimi K2.6 wrote the initial Cortex viewer: Three.js brain mesh, per-vertex BOLD animation, narration panels
- Claude Code reviewed, integrated, and committed

**Cortex-bridge skill:** `/scan <media_file>` — submits a clip to the Cortex API from the Mercury terminal, streams TRIBE v2 progress, and displays the narration on scan complete.

**Related repos:**
- [AlexiosBluffMara/cortex](https://github.com/AlexiosBluffMara/cortex) — TRIBE v2 + Gemma 4 brain-response system
- [AlexiosBluffMara/gemma4-pipeline](https://github.com/AlexiosBluffMara/gemma4-pipeline) — Gemma 4 fine-tune pipeline

---

## Quick Start (this machine)

```bash
# Start interactive chat (connects to local Ollama automatically)
mercury chat

# Start the Discord gateway (Snowy The Bot)
mercury gateway run -v

# Check status
mercury config show
```

**Start the Cortex brain viewer (sister project):**
```bash
# Windows — from D:/cortex/
source C:/Users/soumi/cortex/.venv/Scripts/activate
uvicorn webapp.server:app --host 0.0.0.0 --port 8765 --reload
# open http://localhost:8765
```

**Monitor LoRA training:**
```bash
tail -f ~/gemma4-pipeline/gemma4-pipeline/rtx-5090/logs/train.log
```

---

## Persona (SOUL.md)

Mercury runs as **Snowy The Bot** (Discord: `abmsnowy`) — direct, autonomous, dry-witted. Persona configured in `~/.mercury/SOUL.md`. Acts first, explains after. On other surfaces the bot may surface as **ABM Hermes** depending on gateway configuration.

---

## MCP Servers

| Server | Purpose |
|---|---|
| `@modelcontextprotocol/server-filesystem` | Full home-dir file access |
| `@modelcontextprotocol/server-github` | Repo management (AlexiosBluffMara org) |
| `@modelcontextprotocol/server-memory` | Knowledge-graph persistent memory |
| `@upstash/context7-mcp` | Library docs lookup |
| `@modelcontextprotocol/server-sequential-thinking` | Multi-step planning |

---

## Fallback Providers

When local Ollama is unavailable:

| Provider | Key source | Model |
|---|---|---|
| Gemini | `GOOGLE_API_KEY` (Windows system env) | gemini-2.5-pro |
| GitHub Copilot | `GITHUB_PERSONAL_ACCESS_TOKEN` | copilot default |

---

## Training Pipeline

LoRA fine-tune in progress on the RTX 5090:

- **Base model:** `unsloth/gemma-4-E4B-it` (4-bit BnB, ~9.6GB)
- **Training data:** TRIBE v2 narration turns (General / College / Clinical tier pairs)
- **Framework:** Unsloth 2026.4.8 + TRL 0.24.0 + `get_chat_template("gemma-4")`
- **Output:** `cortex-gemma-4-e4b` — domain-specialized for brain-response narration

Post-training: export → GGUF → `ollama create cortex-gemma-4-e4b`

---

## Repository Structure

```
D:/mercury/           <- this repo (Hermes agent fork)
~/.mercury/           <- runtime config, memories, SOUL.md, state
D:/cortex/            <- TRIBE v2 + Gemma 4 brain-response system (sister project)
~/gemma4-pipeline/    <- LoRA training pipeline fork
```

---

## Hackathon

**Nous Research + Kimi Hackathon — Creative** (due May 3, 2026)

Submission: Mercury as the orchestrator for Cortex — a multimodal brain-response analysis system running entirely on local hardware, using TRIBE v2 (Meta's brain foundation model) + Gemma 4 E4B for cortical activation prediction and multi-audience narration.

---

## Try it yourself

> Heads up: Mercury runs the AI on **your own GPU**. There is no public hosted version — partly because hosting a 5090 for the internet is expensive, and partly because the whole point of Mercury is local-first privacy. The architecture diagram and demo video on this page are real, but to actually chat with the agent you need to clone, install, and bring your own hardware.

### What you need

- An NVIDIA GPU with **at least 12 GB of VRAM** (Mercury was built and tested on an RTX 5090; a 4090, 3090, or any 12 GB+ card works for the smallest model).
- **Python 3.11 or newer** ([download here](https://www.python.org/downloads/)).
- **Ollama** to run the language models locally ([download here](https://ollama.com/download)).
- Roughly **30 GB of disk space** for the model weights.

You don't need an API key for anything to get the basic agent running — the default brain is Gemma 4 E4B, fully local. Kimi K2.6 via the Nous Portal was used for the original hackathon sprint only; production runs entirely on local hardware.

### Setup, copy-paste-able

```bash
# 1. Clone Mercury
git clone https://github.com/AlexiosBluffMara/mercury
cd mercury

# 2. Make a Python environment for it
python -m venv .venv
# Mac/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 3. Install Mercury
pip install -e .

# 4. Pull the local AI models (this takes a while — ~10 GB download)
ollama pull gemma4:e4b           # the fast everyday brain
ollama pull embeddinggemma:300m  # for memory and search

# 5. Talk to it
mercury chat
```

That's it. Type a question. It thinks on your GPU, replies in your terminal.

### Optional: the Discord / iMessage / WhatsApp surfaces

Mercury can also act as a Discord bot, an iMessage relay, or a WhatsApp bot. Each takes ~5 minutes to wire up — see `mercury setup` for the interactive walkthrough.

### Optional: the brain visualizer (the thing in the demo video)

The 3D brain viewer in the demo lives in a sister project, [Cortex](https://github.com/AlexiosBluffMara/cortex). Mercury talks to it through a skill called `cortex-bridge`. To run that yourself:

```bash
git clone https://github.com/AlexiosBluffMara/cortex
cd cortex && pip install -e .
cortex serve --port 8765   # opens the brain viewer
```

Then point Mercury at it (`mercury config` → `cortex_url: http://localhost:8765`). The full pipeline (video in → brain prediction → narration out) takes ~6 minutes per scan.

---

## License

MIT — see [LICENSE](LICENSE).

Fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) by Nous Research.
Adapted by [Alexios Bluff Mara LLC / Red Team Kitchen](https://github.com/AlexiosBluffMara).
