# Mercury — Nous Research Mercury Agent Creative Hackathon Submission

> **Mercury is a Mercury Agent fork that turns any short video into a 3D cortical
> activation map with three-tier narration, all on consumer hardware, using
> Kimi K2.6 + Mercury 4 405B + Gemma 4 in concert.**

- **Hackathon:** [Nous Research Mercury Agent Creative Hackathon](https://x.com/NousResearch/status/2039740198259462370) ($25K main + $5K Kimi Track)
- **Submission deadline:** May 3, 2026
- **Repository:** [github.com/AlexiosBluffMara/mercury](https://github.com/AlexiosBluffMara/mercury) (MIT)
- **Tagged release:** `v0.2.0-nous-creative` (TBD before submission)

---

## TL;DR for the Judges

You drop a 20-second cat video into Mercury (via CLI, WebUI, Discord, or
WhatsApp). Mercury orchestrates four models across two clouds and one
desktop GPU:

1. **Gemma 4 E4B** (local Ollama on the RTX 5090) vision-gates the input
2. **Mercury 4 405B** (Nous Portal) plans the tool sequence
3. **TRIBE v2** (the Gallant-Lab brain-foundation model, on the same
   5090 via a hard GPU swap) predicts a 20,484-vertex × 100-timepoint BOLD
   response
4. **Kimi K2.6** (Nous Portal) writes the three-tier narration —
   toddler / clinician / researcher

You get back **one URL**. Open it and there's a 3D cortex animating with the
predicted activation, three tier-tabs of narration alongside, and a
region-inspector that lets you click any cortical region for its individual
response curve.

Nothing leaves the machine that you didn't put on the network yourself.
The web demo is reachable via Tailscale (your tailnet only) or via a
Cloudflare-Tunnel-fronted Cloud Run instance for public showcasing.

---

## Why Mercury Is a Creative-Track Submission

The hackathon's call: *"video, image, audio, 3D, long-form writing, creative
software, interactive media."* Mercury sits at the intersection of three
of those — **video → 3D → long-form writing** — with the Mercury Agent
loop as the connective tissue:

| Creative axis | What Mercury does |
|---|---|
| **Video** | Accepts arbitrary 20–50-s clips as input |
| **3D / interactive media** | Three.js + R3F cortex viewer with vertex-color BOLD overlay (`fmri-overlay` skill) |
| **Long-form writing** | Three-tier explanatory narration for every scan (toddler, clinician, researcher) |
| **Creative software** | One Mercury Agent, four models, three platforms, *that the user can extend* — every chained capability is a skill in `skills/` |

The cortex is *the canvas*. The agent is *the brush*. The judge's video is
*the prompt*. Genuinely new creative territory — the public skill registries
(MercuryHub, awesome-mercury-agent) had **almost nothing for 3D + neuroscience**
before this submission.

---

## Architecture

```
                     ┌──────────────────────────────────────────────┐
                     │  Mercury Mercury Agent (RTX 5090, Windows)    │
                     │                                              │
                     │  CLI ◄──┐    WebUI ◄─┐   gateway:            │
                     │         │            │     • Discord         │
                     │   ┌─────┴─────┐      │     • WhatsApp        │
                     │   │ Mercury 4  │      │     • Telegram        │
                     │   │ 405B      │      │     • Slack           │
                     │   │ (planner) │      │                       │
                     │   └─────┬─────┘      │                       │
                     │         ▼            │                       │
                     │  ┌──────────────┐    │                       │
                     │  │ Skill Loop   │◄───┘                       │
                     │  │ • brain-viz  │ ←─────────┐                │
                     │  │ • fmri-      │           │                │
                     │  │   overlay    │           │                │
                     │  │ • cortex-    │           │                │
                     │  │   bridge     │           │                │
                     │  │ • discord-   │           │                │
                     │  │   bot        │           │                │
                     │  │ • tailnet    │           │                │
                     │  └──────┬───────┘           │                │
                     │         │                   │                │
                     │         ▼                   ▼                │
                     │  ┌──────────────┐   ┌─────────────────┐      │
                     │  │ Kimi K2.6    │   │ GPU Scheduler   │      │
                     │  │ (Nous Portal)│   │ Gemma 4 ⇄ TRIBE │      │
                     │  │ • coder      │   │ • Cortex API    │      │
                     │  │ • narration  │   │ • Three.js view │      │
                     │  └──────────────┘   └─────────────────┘      │
                     └──────────────────────────────────────────────┘

                    Tailnet ──► Pixel 9 Pro Fold ─ on-device Gemma 4 E4B
                            ──► Mac Mini M4      ─ MLX Gemma 4 12B fallback
                            ──► Cloud Run        ─ public-fronted webapp
```

The brains route by capability:

- **Mercury 4 405B** plans the tool sequence (which skills, in what order,
  what GPU window). Native function-calling = ideal for the agent loop.
- **Kimi K2.6** writes the actual code and the long-form narration. Top-tier
  open-weight on SWE-Bench Pro (58.6%) and excellent at instruction-following
  for the three-tier narration prompt.
- **Gemma 4** stays local on the 5090 for everything that benefits from
  zero-network: vision-gating, fast classification, embedding queries against
  the user's local memory store.
- **TRIBE v2** is the brain-foundation model itself, swapped in/out of VRAM
  by Cortex's `GPUScheduler` so it never coexists with Gemma 4 E4B (32 GB
  isn't enough for both).

## Skills That Land With This Submission

| Skill | Path | Lines | Purpose |
|---|---|---|---|
| `brain-viz` | `skills/creative/brain-viz/` | declarative | Compose the full pipeline |
| `fmri-overlay` | `skills/creative/fmri-overlay/` | declarative + GLSL | BOLD timeseries → animated cortex |
| `cortex-bridge` | `skills/cortex/cortex-bridge/` | existing | Drives Cortex's `brain_scan` / `narrate` |
| `discord-bot` | `skills/platforms/discord-bot/` | declarative | Slash-command surface for the brain pipeline |
| `tailnet` | `skills/network/tailnet/` | config + docs | Identity-aware private mesh |
| `three-js-component`, `three-js-debug`, `glsl-shader` | `skills/3d/` | existing | The 3D primitives the above compose |

Plus the Claude→Kimi orchestration helper at `tools/kimi_dispatch.py` —
the meta-tool that lets a Claude-led tech lead dispatch code-gen to Kimi
K2.6 cleanly.

## Reproducibility

```bash
# 1) Install Mercury (Mercury Agent fork)
git clone https://github.com/AlexiosBluffMara/mercury
cd mercury && python -m venv .venv && source .venv/bin/activate
pip install -e .[all]

# 2) Wire Cortex (the brain backend)
git clone https://github.com/AlexiosBluffMara/cortex
pip install -e ../cortex

# 3) Pull the local LLMs Mercury talks to
ollama pull gemma4:e4b   gemma4:26b   embeddinggemma:300m

# 4) Configure Nous Portal (one of):
#    a) Run `mercury setup` and pick "Nous" interactively, OR
#    b) Add the API-key custom provider:
mercury auth add nous --type api-key --api-key sk-...
# Then add to ~/.mercury/config.yaml:
#   custom_providers:
#     - name: nous-portal
#       base_url: https://inference-api.nousresearch.com/v1
#       key_env: NOUS_API_KEY
#       api_mode: chat_completions
#   model:
#     default:  moonshotai/kimi-k2.6
#     provider: nous-portal

# 5) Start everything
cortex serve --port 8766 &        # brain backend
mercury gateway up discord &      # if using the bot
mercury dashboard                 # opens the WebUI on the tailnet

# 6) Try it
mercury -z "show my brain on this clip" --skills brain-viz \
        --attach /path/to/clip.mp4
```

## Demo Video — 3-Minute Recording Plan

| Time | Beat | What's on screen |
|---|---|---|
| 0:00 | Title card | "Mercury — Mercury Agent + Cortex. RTX 5090, no cloud." |
| 0:10 | Show the agent waking up | `mercury` TUI; `mercury status` shows all four brains green |
| 0:25 | First scan — cat video | Drop video into `/brain` Discord command. Bot replies "scanning…" |
| 0:50 | GPU swap visualization | `nvidia-smi -l 1` in side terminal — Gemma drops, TRIBE v2 loads |
| 1:30 | Result delivered | Discord embed with viewer link. Click. Three.js cortex animates. |
| 1:50 | Three tiers side-by-side | Click toddler / clinician / researcher tabs |
| 2:10 | A/B comparison | `fmri-overlay` skill: cat video vs. metronome side-by-side |
| 2:30 | Multi-model swap | `/model nous-portal:nousresearch/mercury-4-405b` → re-narrate at researcher tier with Mercury 4 |
| 2:45 | Kimi Track moment | `/model nous-portal:moonshotai/kimi-k2.6` — re-write a paragraph in Kimi's voice |
| 2:55 | Outro card | Repo URL, license, "Gemma is a trademark of Google LLC." |

## Submission Deliverables Checklist

- [ ] **Tweet** tagging `@NousResearch` and `@Kimi_Moonshot` with demo video link
- [ ] **Discord post** in `#creative-hackathon-submissions` with tweet URL
- [ ] **Public open-source GitHub repo** at `AlexiosBluffMara/mercury` with:
  - [x] MIT license inherited from upstream Mercury
  - [x] README banner + quickstart
  - [x] `docs/NOUS_HACKATHON.md` (this file)
  - [ ] `BENCHMARKS.md` — measured numbers, model comparison
  - [ ] Demo video committed or linked
  - [ ] Architecture diagram as `docs/architecture.svg`
  - [ ] CONTRIBUTING.md updated with skill-PR conventions
- [ ] **Tagged release** `v0.2.0-nous-creative` on the day-of
- [ ] **`.env.example`** documenting every required env var (`NOUS_API_KEY`,
      `DISCORD_BOT_TOKEN`, `CLOUDFLARE_API_TOKEN`, `GOOGLE_API_KEY`)
- [ ] **Trademark + license file**: "Gemma is a trademark of Google LLC."
      and CC-BY-NC notice for TRIBE v2 weights

## Dependencies and Licenses

| Component | Source | License |
|---|---|---|
| Mercury (this repo) | Red Team Kitchen / fork of `NousResearch/hermes-agent` | MIT |
| Mercury Agent | NousResearch | MIT |
| Cortex (brain backend) | Red Team Kitchen | Apache-2.0 |
| TRIBE v2 weights | Gallant Lab, UC Berkeley | **CC-BY-NC 4.0** (non-commercial) |
| Gemma 4 weights | Google LLC | Gemma Terms (attribution required) |
| Kimi K2.6 (API access only) | Moonshot AI via Nous Portal | API ToS |

The non-commercial framing is consistent across all surfaces — this is a
hackathon / research / education submission, not a commercial product.

## Hard Invariants (Quoted from `CLAUDE.md`)

These rules apply to every contribution to this repo:

1. **No `Co-Authored-By: Claude`** in commits. Match upstream Mercury
   conventional-commit style.
2. **No "Generated by [AI]"** comments anywhere in code.
3. **No unprovoked docstrings** — comment only when the *why* is non-obvious.
4. **Tailnet-only WebUI.** Never `tailscale serve --funnel`.
5. **Cortex GPU lock.** Mercury never loads Gemma into VRAM while TRIBE
   v2 is hot.
6. **`duration_trs` is hard-locked at 100 TRs (50 s @ 2 Hz).** Don't
   override.
7. **Kimi K2.6 is the default coder; Mercury 4 405B is the default planner.**
   Other providers are fallbacks, not first choices.

— Soumit Lahiri (Red Team Kitchen / Alexios Bluff Mara LLC), Apr 2026
