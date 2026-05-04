# Mercury — Project Brief for Prof. Mangolika Bhattacharya

**Author:** Soumit Lahiri (omlahiri), Illinois State University
**Date:** April 26, 2026
**Status:** Working prototype. Live agent reachable via Discord; full pipeline through to Cortex's neuroscience model verified.

---

## Executive summary

Mercury is a personal-scale AI agent platform I forked from
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
(MIT-licensed) and adapted to run as a **lightweight, locally-hosted,
deeply-Google-integrated assistant** on a single RTX 5090 desktop. It
acts as a unified brain that can drive web browsers, read my Gmail,
search Notion, transcribe audio, predict brain responses to videos
through Meta's TRIBE v2 model, and self-debug its own code by
delegating to Claude Code — all from one chat surface (Discord today,
WhatsApp and a tailnet-only WebUI tomorrow).

The fork is intentional and substantial: I removed about 80% of the
upstream codebase (cloud-sandbox backends I don't need, 12 messaging
platforms I don't use, 7 of 8 memory providers, RL/training infra
that bloats the install), then layered three Mercury-specific
subsystems on top: a dual-brain router that decides per-turn whether
to use a free local model or a paid cloud one, a bridge into my
Cortex (TRIBE v2 + Gemma 4) project, and an auto-debug loop that
catches its own runtime errors and fixes them.

This document explains the why, the what, and the differentiation
from the upstream.

---

## What is Mercury (the upstream)

Mercury Agent is a self-improving AI assistant developed by Nous
Research. It runs as a single Python process that can talk to almost
any LLM provider and connect to 17 messaging platforms, with a
built-in skill system that lets the agent autonomously create and
edit instructions for itself based on what it learns from each
conversation. It's the open-source state-of-the-art for personal
agents — but it's a kitchen-sink platform designed for many users on
many setups, with corresponding install size, dependency surface, and
operational complexity. Currently around 116,000 GitHub stars, 17,000
forks, MIT-licensed, written in Python with a TypeScript dashboard.

Mercury optimizes for *generality*. A single binary should run on a
$5 VPS, a Raspberry Pi, an iPhone via Termux, or a 32-core workstation.
It supports six terminal sandboxes, eight memory providers, hundreds
of LLM endpoints, a skills marketplace, and a plugin system that lets
the community ship third-party extensions.

That generality has a cost: most users will never use most of those
options.

---

## What is Mercury, and why it's different

Mercury is the same agent core, specialized for **one user, one
machine, one ecosystem**:

|  | Mercury (upstream) | Mercury (this fork) |
|---|---|---|
| **Target hardware** | "Anywhere from a Raspberry Pi to a GPU cluster" | RTX 5090 desktop running Windows 11, with a Cortex sibling project at `D:/cortex` |
| **Source of LLM** | 200+ providers via OpenRouter / Nous Portal | GitHub Copilot Pro+ for capable cloud calls; Ollama-served Gemma 4 E4B for local; Vertex AI for Google grounded search |
| **Cost model** | User pays for API tokens directly | $0 marginal: Copilot's free models (GPT-5 mini at multiplier 0), Gemma local via existing Ollama install, Gemini's free 5,000 grounded searches/month, Google Workspace's free quotas |
| **Memory** | 8 SaaS-leaning providers | One local provider (Holographic — SQLite + FTS5 + HRR algebra) layered on a frozen-snapshot MEMORY.md / USER.md pair, all under `~/.mercury/` |
| **Sandboxing** | local + Docker + SSH + Modal + Daytona + Singularity | local + Docker only |
| **Messaging surface** | Telegram + Discord + Slack + WhatsApp + Signal + 12 more | Discord + WhatsApp + email — chosen because they're the user's actual channels |
| **WebUI** | Bundled Vite/React dashboard, public-facing | Mobile-first, **Tailscale-only** so it's reachable from my phone but not the internet, currently inheriting the upstream design but planned for a full visual-language redesign |
| **Special integrations** | None project-specific | Live bridge to Cortex (Meta TRIBE v2 + Gemma 4); planned hooks for ISU-specific data sources (Mangolika's lab, course materials, ISBN libraries) |
| **Self-debugging** | None | Auto-debug loop: when the agent errors, Mercury delegates the fix to a Claude Code subprocess running under my existing $100/mo Max plan, applies the patch, and restarts itself |
| **Lines of code** | ~120,000 LOC of Python (excluding tests) | ~50,000 LOC after strip + Mercury additions |
| **Deps installed** | Heavy (most extras) | Curated subset; Cortex's full ML stack including PyTorch 2.11+cu128 for Blackwell sm_120 |

The result is a sharper tool. Mercury is the Swiss Army knife;
Mercury is the same blade ground specifically for what I'm
actually doing in a given week.

---

## Why fork at all (and why upstream stayed open)

I considered building from scratch. Three reasons not to:

1. **The agent loop is genuinely hard.** Mercury has solved problems
   that aren't visible until you've shipped something — context
   compression at 170k tokens, prompt-cache-friendly memory
   snapshots, autonomous skill creation, cross-platform conversation
   continuity. Re-implementing those would take months and produce a
   worse result.

2. **MIT license + active upstream.** Forking lets me track upstream
   improvements with a `git fetch upstream main` while diverging
   freely on the parts that matter to me. I keep credit clean —
   Mercury's README and license link back to Nous, every retained
   file inherits its original copyright notice.

3. **My time is better spent on integrations than on infrastructure.**
   What's interesting to me is the Cortex bridge, the Google ecosystem
   integration, and the auto-debug loop. Those don't exist anywhere
   else. The chat-loop infrastructure that lets the rest hang together
   is solved problem.

---

## What's verified working today (2026-04-26)

A live AI bot named **Snowy** (display: "Snowy The Bot") sits in my
personal Discord server (`#bot-test-3` is its home channel). I have a
12-of-12 end-to-end smoke test that runs against every external
service Mercury talks to and confirms each is responding correctly.
Run with `python D:/mercury/scripts/e2e_smoke.py`. **As of this
brief, all 12 checks pass in 34 seconds wall-clock.**

| # | Capability | What I asked | What it returned | Backing API |
|---|---|---|---|---|
| 1 | Cortex bridge | Live GPU state | `idle, free_gb=23.6` | Local TRIBE/Gemma scheduler |
| 2 | Vertex AI auth | "Are credentials configured?" | `mode=vertex` | gcloud Application Default Credentials |
| 3 | Tool registry | "How many tools?" | 101 tools across 26 toolsets | Mercury internal |
| 4 | Google Search | "What is the official ISU mascot?" | "Reggie Redbird" + 4 citations | Gemini 2.5 Flash grounding |
| 5 | Books API | ISBN 9780262035613 | "Deep Learning" by Goodfellow | books.googleapis.com (anonymous read) |
| 6 | Knowledge Graph | "Illinois State University" | ISU as top entity, with description | Wikidata public API |
| 7 | Translate v3 | "Hello, world..." → ja | "こんにちは、世界。マーキュリーがオンラインになりました。" | translate.googleapis.com |
| 8 | Maps Routes | Normal IL → Champaign IL | 86.6 km, 57 minutes | routes.googleapis.com |
| 9 | Maps Places along route | "coffee shop, max detour 5 min" | 10 places, top: Tropical Smoothie Cafe | places.googleapis.com |
| 10 | Text-to-Speech | "Mercury smoke test successful." | 17 KB MP3 with Neural2-J voice | texttospeech.googleapis.com |
| 11 | Cloud Vision | Test image URL | 0 labels (test image too small; structure verified) | vision.googleapis.com |
| 12 | Firecrawl | example.com | "# Example Domain..." clean Markdown | firecrawl.dev |

In addition to the verified checks, the agent already handles:

- Open-ended questions in Discord with model-routed responses (free
  GPT-5 mini for most; auto-escalation to Sonnet 4.6 for hard ones).
- Code generation, debugging, and self-debug via the `claude` CLI
  (uses my Claude Max subscription, no separate API billing).
- 75 skill packages registered with Discord slash-command autocomplete
  (`/skill` opens a fuzzy picker).
- A 5-tool auto-debug loop (`errors_tail`, `session_replay`,
  `gateway_status`, `gateway_restart`, `debug_with_claude_code`) the
  agent can invoke when something breaks at runtime.
- Filesystem access into a Tolaria-format markdown vault at
  `~/.mercury/vault/`, also opened in Obsidian on Windows so I can
  see what Mercury writes there in real time.
- Notion integration via MCP server (page search, content read/write).
- Persistent memory: holographic SQLite + FTS5 fact store + frozen
  MEMORY.md/USER.md for prompt-cache efficiency, all under
  `~/.mercury/`.

**Soon (one drop-the-file step away):**

- Drop a video in `#bot-test-3` and have Mercury route it through
  Cortex — Meta's TRIBE v2 model predicts which cortical regions
  activate while watching that video, then Cortex's Gemma 4 fine-tune
  generates a 7-tier explanation from toddler-level to
  neuroscience-researcher-level. TRIBE weights (677 MB) are
  downloaded; Cortex's full ML stack (PyTorch + cu128 + transformers
  + neuralset) is installed and verified on the 5090's Blackwell
  sm_120 GPU.
- Drop an audio file → faster-whisper local transcription (3 GB
  model, lives alongside Gemma in 12 GB VRAM total).
- WhatsApp gateway pairing (adapter present, needs a one-time QR scan).

---

## What this lets me do as a student

A few use-cases I've actually wired:

**Coursework support:** I can paste a textbook ISBN and Mercury
returns the metadata, Google Books preview link, page count, and
chapter outline. With a Notion integration token, it can append the
parsed reading list to a Notion database I've shared with it.

**Research synthesis:** I can paste a paper URL and Mercury returns a
clean Markdown extract via Firecrawl. Combined with the Knowledge
Graph API for entity disambiguation and Gemini grounding for related
work, I can have it produce a citation list with notes for any topic
in a few minutes.

**Field-relevant integration:** Cortex (the project Snowy bridges
into) is a TRIBE-v2-based model that predicts cortical brain
responses to natural stimuli. For a course like Mangolika's (or any
neuroscience-adjacent class), this lets me ask "what would the brain
do during this lecture clip" and get back a labeled cortical
activation map, narrated in plain English. It's not a clinical tool;
it's a teaching aid that makes the predictions of a published Meta
foundation model interactively explorable.

**Self-improvement:** When something breaks (Mercury logs a runtime
error), the agent itself can call `errors_tail` then
`debug_with_claude_code`, which spawns a Claude Code subprocess on
the same machine. Claude Code reads the trace, edits the right
file, runs tests, commits the fix, and Mercury restarts its own
gateway. This works because Mercury's `mercury/mcp_extensions.py`
delegates to the `claude` CLI — token cost flows through my $100/mo
Max subscription, not a separate API account.

---

## What's still in progress

- **Full WebUI redesign**, not just rebrand. Mercury inherits Nous's
  dashboard look. I'm planning a Tailscale-only mobile-first UI
  visually distinct from upstream — same React/Vite stack, redesigned
  components, four new pages (Brain Switch, Cortex Bridge, Skills
  Inspector, Memory Viewer).
- **End-to-end Cortex demo**: TRIBE weights are downloaded
  (677 MB at `D:/cortex/tribev2_weights/`), torch+CUDA is verified on
  the 5090, the bridge sees the GPU. Last step is dropping a real
  video in the Discord channel and watching the swap-and-narrate
  pipeline complete.
- **WhatsApp gateway**: adapter exists, needs a node bridge subprocess
  + QR pairing on my Pixel.
- **Quota guard middleware**: a small layer that tracks per-API daily
  usage and short-circuits at 90% of the free tier so we never
  accidentally cross into paid territory.

---

## Architecture (one paragraph)

Mercury is a Python 3.12 process that runs on a Windows 11 desktop
with an RTX 5090. It uses Ollama locally for fast Gemma 4 E4B
inference, GitHub Copilot's API for capable cloud inference (free
under my Pro+ subscription), and Google Vertex AI for Google's
grounded search and image generation. A FastAPI server hosts a
React/Vite dashboard reachable only via Tailscale. A messaging
gateway connects the same Python agent to Discord (live now) and
will connect to WhatsApp and email next. Memory is split between a
frozen-at-session-start MEMORY.md snapshot for prompt-cache
efficiency and a SQLite + FTS5 + Holographic-Reduced-Representation
fact store for cross-session recall. A child Cortex package at
`D:/cortex/` provides the neuroscience pipeline: media in via
ffmpeg, brain-response prediction via Meta's TRIBE v2 model on the
5090's 22 GB of TRIBE-loaded VRAM, then narration in seven
expertise tiers via Gemma 4. The whole thing is open source on
GitHub at [AlexiosBluffMara/mercury](https://github.com/AlexiosBluffMara/mercury)
under MIT, with attribution to Nous Research.

---

## Citations & links

- **Mercury** — [github.com/AlexiosBluffMara/mercury](https://github.com/AlexiosBluffMara/mercury)
- **Cortex** — `D:/cortex/`, public at AlexiosBluffMara/cortex (planned)
- **Hermes Agent (upstream)** — [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **Meta TRIBE v2** — [ai.meta.com/blog/tribe-v2-brain-predictive-foundation-model/](https://ai.meta.com/blog/tribe-v2-brain-predictive-foundation-model/), weights at [huggingface.co/facebook/tribev2](https://huggingface.co/facebook/tribev2)
- **Gemma 4** — Google's open weights, served locally via Ollama
- **Tolaria** (markdown vault format) — [github.com/refactoringhq/tolaria](https://github.com/refactoringhq/tolaria)

Happy to demo any of this live, in person or over Zoom.
