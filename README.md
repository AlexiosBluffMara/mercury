<p align="center">
  <img src="assets/banner.svg" alt="Mercury — local-first dual-brain agent" width="100%">
</p>

# Mercury

> **Fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) (MIT) by [Red Team Kitchen](https://github.com/AlexiosBluffMara).**
> Submitted to the **Nous Research + Kimi Hackathon — Creative category** (due May 3, 2026).

---

## What Mercury Is

Mercury is a local-first autonomous agent running on an RTX 5090 desktop. It is the operational brain behind **[The Academy / Project Oldstones](https://github.com/AlexiosBluffMara/JennyOfOldstones)** — a system that ingests 20 years of Facebook Messenger data and creates RAG-backed ghost personas of real people, anchored to their actual life eras, voice patterns, and emotional arcs.

The creative submission is Mercury acting as the agent that *inhabits* these personas — driving them, orchestrating the data pipeline, and responding to queries as the people in the dataset would have responded at a given point in their lives.

---

## Models (RTX 5090 — local Ollama)

| Role | Model | Capability |
|---|---|---|
| Default / Vision / Multimodal | `gemma4:e4b` | completion · vision · audio · tools · thinking |
| Deep reasoning / long context | `gemma4-26b-moe:latest` | completion · tools · thinking |
| Fine-tuned persona model (in training) | `gemma4-soumit-persona` | LoRA on 70K JennyOfOldstones turns |

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

## The Academy — Creative Submission

**Project Oldstones** is a second-brain / digital-memory system built on ~362,000 Facebook Messenger messages spanning 2003–2026:

- **SQLite + LanceDB** — 362K messages, 3072-dim Gemini Embedding 2 vectors
- **Ghost personas** — RAG + era summaries + cross-person temporal echoes
- **Life era grounding** — 22 eras (per-semester Purdue, HS summers, India childhood) anchoring every memory retrieval to real biographical context
- **Voice profiles** — 654 people profiled; 7 focus personas with full emotional arcs
- **3D visualization** — Three.js / R3F: Timeline Nebula (60K particle field), Relationship Galaxy (135 nodes), Ghost Chat portal
- **LoRA fine-tune** — Gemma 4 E4B trained on 70K persona-formatted conversation turns

Mercury drives the ghost chat endpoint, orchestrates the embedding pipeline, and serves as the demo agent for the hackathon presentation.

---

## Quick Start (this machine)

```bash
# Mercury is installed in WSL2 Ubuntu
# Start interactive chat (connects to local Ollama automatically)
~/mercury/.venv/bin/mercury chat

# Check status
~/mercury/.venv/bin/mercury status
```

**Start the Academy backend + frontend:**
```bash
# Windows — from JennyOfOldstones/
start_api.bat          # FastAPI :8765
cd viz && npm run dev  # Vite :5173
```

**Monitor LoRA training:**
```bash
# WSL2
tmux attach -t training
# or
tail -f ~/gemma4-pipeline/gemma4-pipeline/rtx-5090/logs/train.log
```

---

## Persona (SOUL.md)

Mercury runs as **Artemis** — direct, autonomous, dry-witted. Configured in `~/.mercury/SOUL.md`. Acts first, explains after.

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

LoRA fine-tune running in `tmux:training` on WSL2:

- **Base model:** `unsloth/gemma-4-E4B-it` (4-bit BnB, ~9.6GB)
- **Training data:** 70,034 JennyOfOldstones persona turns (role/content chat format)
- **Eval data:** 17,509 held-out turns
- **Framework:** Unsloth 2026.4.8 + TRL 0.24.0 + `get_chat_template("gemma-4")`
- **Output:** `~/gemma4-pipeline/gemma4-pipeline/rtx-5090/outputs/gemma4-soumit-persona/`

Post-training: export → GGUF → `ollama create gemma4-soumit-persona`

---

## Repository Structure

```
~/mercury/                           <- this repo (Hermes agent fork)
~/.mercury/                          <- runtime config, memories, SOUL.md, state
~/gemma4-pipeline/                   <- LoRA training pipeline fork
C:/Users/soumi/JennyOfOldstones/     <- Academy data pipeline + Three.js frontend
```

---

## Hackathon

**Nous Research + Kimi Hackathon — Creative** (due May 3, 2026)

Submission: Mercury as the agent powering The Academy ghost personas — a 20-year digital-memory system running entirely on local hardware, using Gemma 4 E4B (multimodal: vision + audio + tools + thinking) and a LoRA fine-tuned persona model for authentic temporal persona simulation.

---

## License

MIT — see [LICENSE](LICENSE).

Fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) by Nous Research.
Adapted by [Alexios Bluff Mara LLC / Red Team Kitchen](https://github.com/AlexiosBluffMara).
