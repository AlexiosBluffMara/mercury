# Gemma 4 Good Hackathon — submission readiness audit

**Updated:** 2026-05-06 (deadline 2026-05-18 — **12 days out**)
**Track:** Digital Equity (primary). Health and Education are adjacent fits.
**Repos:** [Mercury](https://github.com/AlexiosBluffMara/mercury) (gateway/agent), [Cortex](https://github.com/AlexiosBluffMara/cortex) (TRIBE v2, brain-response analysis)

## What Kaggle wants in the box

Per the Kaggle competition page and announcement coverage:
1. **Working demo** (deployed and runnable)
2. **Public code repo** with permissive license
3. **Technical write-up** explaining what was done and how Gemma 4 is applied
4. **Short demo video** showing real-world use

Judging weights three areas: **Impact & Vision**, **Video Pitch & Storytelling**, **Technical Depth & Execution**. The official line is *"the winners will not necessarily be the people with the most complicated architecture"* — practical impact wins.

## Status by deliverable

| Deliverable | Status | Owner | Note |
|---|---|---|---|
| Working demo (Mercury + Cortex live) | **80%** | local stack done; cloud-failover roadmap documented; needs link in submission | Big Apple 3 ports + Seratonin Ollama + WebUI all run today |
| Public Mercury repo | **95%** | top-level README is from the Nous hackathon era | Refresh README to lead with Gemma 4 Good story |
| Public Cortex repo | **90%** | README current; TRIBE v2 model card needs link | Mostly already there |
| Technical write-up | **0%** | not started | **Highest leverage gap.** Draft below |
| Demo video | **0%** | scripted in `scripts/record_mercury_demo.py` but never recorded cleanly | Re-record after WebUI redesign and OpenRouter wiring |
| Kaggle submission entry | **0%** | account exists but no notebook | Needs a Kaggle notebook entry |

## What's actually working (what to show)

- **Mercury Gateway** — Python agent fork with five clients: Discord, WhatsApp, terminal TUI, web UI, Cron
- **Local inference** on Big Apple (M4 Max 48 GB) — three MLX servers via mlx-vlm 0.5.0:
  - port 8080: E4B Unsloth UD-MLX-4bit (audio + vision multimodal)
  - port 8081: 26B-A4B Unsloth UD-MLX-4bit (MoE, 4B active)
  - port 8082: 31B Unsloth UD-MLX-4bit (deep reasoning)
- **Local inference** on Seratonin (RTX 5090, 32 GB VRAM) — Ollama 0.23.1:
  - `gemma4:e4b` (194 tok/s on CUDA)
  - `cortex-gemma-4-e4b:latest` (TRIBE v2 — fine-tuned cortex specialist)
  - `embeddinggemma:300m` for retrieval
- **Cloud failover** — OpenRouter free tier wired with $20-credit-unlocked 1000 reqs/day cap; paid pool gated behind `--allow-paid` flag
- **Cortex (D:\cortex)** — TRIBE v2 brain-response prediction, 20,484 cortical voxels, three.js cortex viewer, Cloudflare Pages deployment at `redteamkitchen.com/cortex/`
- **Cross-device** — Pixel Fold Discord client, iPhone Discord client, Mac TUI, Windows WebUI, Pi 5 4K kiosk
- **Cortex lights** — Hue automation green/amber/red on agent activity (Soumit's request earlier today)
- **Premium WebUI redesign** — Inter font, indigo accent, glass morphism sidebar, bottom mobile nav, section visibility toggles

## What I'm cutting (post-deadline roadmap)

These were started but not load-bearing for the May 18 submission:

- **Seratonin NVFP4 + MTP** — repeated download stalls on the 13 GB NVFP4 weights, hf-transfer choking on parallel chunks. The 2-3× speedup is nice but the demo doesn't need it. **Moved to post-deadline.**
- **Big Apple BF16 E4B + MTP on port 8083** — same story, lower ROI than fixing the submission documents.
- **TRIBE v2 cloud offload** — explicitly post-deadline per Soumit's earlier ask. Will use HF Inference Endpoints when shipped.
- **Modal cloud mirror** — drafted in CLOUD_REPLICATION doc but not implemented.

The story for judges is: **"we have local working today, cloud documented and budgeted, MTP and Modal are the next month's roadmap."** That's stronger than half-shipped MTP.

## What would actually move the needle (next 12 days)

Ranked by impact-per-hour:

### 1. Submission write-up (`SUBMISSION_GEMMA4.md`) — 2-3 hours
The single document a judge actually reads. Should include:
- Headline: "Mercury — Gemma 4 multi-modal agent for Digital Equity, runs $0/month on a teacher's laptop"
- Problem: schools without reliable internet, students without GPU access, AI cost squeeze
- Solution: open-weight Gemma 4 + Mercury gateway + cross-device clients
- Why Gemma 4 specifically: 256K context, native vision/audio, Apache 2.0, multilingual (140+)
- Architecture diagram: local-first hybrid with cloud burst
- Cost comparison: $0 vs $60-200 for an API-only equivalent (numbers from HACKATHON_COSTS doc)
- Demo links: live URLs, video, Kaggle notebook
- What we measured: latency, throughput, accept-rate of cloud failover
- Reproducibility: the README is a single command (`mercury setup`) that gets a teacher to a working chat in ≤5 min

### 2. Demo video — 3-4 hours including takes and edits
Three-minute video showing:
- 0:00–0:30 — TUI: `mercury -z "..."` with Gemma 4 E4B local response
- 0:30–1:00 — WebUI on Mac: native vision (image upload → description)
- 1:00–1:30 — Discord on phone: agent answers across mesh
- 1:30–2:00 — Cortex page: brain response from a 30s clip
- 2:00–2:30 — Failover demo: pull network on Big Apple, show graceful degradation to OpenRouter free
- 2:30–3:00 — Cost overlay: $0 cumulative, lights green throughout

### 3. README polish (top-level Mercury + Cortex) — 1-2 hours
Both READMEs were last edited for the Nous hackathon. Replace the lede with the Gemma 4 Good positioning. Add a one-paragraph "what this is" + a `make demo` command + the architecture diagram from the docs.

### 4. Kaggle notebook entry — 1 hour
Create the actual submission. A Kaggle notebook that:
- Pulls Mercury via `pip install -e git+https://github.com/AlexiosBluffMara/mercury.git`
- Pulls a small Gemma 4 model via Ollama or HF
- Runs three sample inferences (text, vision, audio)
- Embeds the demo video
- Links to public deployment

### 5. Light code refactoring for LLM friendliness — 1 hour
- Make sure every public function in `agent/transports/*` has a docstring with usage example
- Standardize error messages so they say "what happened, what to do next"
- Add a `__doc__` overview at the top of `mercury_cli/__init__.py` that explains the CLI entrypoints
- Optional: split the 600-line `agent/router.py` into `router.py` + `failover.py` + `healthcheck.py`

### 6. Mercury × Cortex integration verification — 30 min
Already wired: `agent/gpu_coordinator.py` checks Cortex GPU state, `mercury_cli/mercury_routes.py` calls `cortex_bridge.cortex_vram_report()`. Just need to verify it works end-to-end and document the contract in one paragraph.

## Effective time budget

Given Soumit's pace and the 12-day window:
- 8 hours focused submission work over the next two weekends
- 4 hours weekday tinkering for demo polish
- 2 hours for the Kaggle notebook + final video render
- = **~14 productive hours before the deadline**

Bullets 1–4 above eat 7-10 hours. That leaves room for one nice-to-have (probably the code refactor, which keeps paying dividends post-hackathon).

## What success looks like on May 18

- Public Mercury repo: green CI, README opens with Gemma 4 Good banner, includes demo video, links to live deployment
- Public Cortex repo: similar, includes link to `redteamkitchen.com/cortex` live page
- Kaggle notebook submission: ~15-cell notebook, every cell self-contained, runs in Kaggle's free GPU env
- 3-minute demo video: posted on YouTube, embedded in submission
- The technical write-up tells a story a non-technical judge can follow, with hard numbers a technical judge can cross-check

## What I am explicitly NOT doing before deadline

- Won't touch Vertex AI / Gemini API (May 1 incident)
- Won't optimize MTP throughput (post-deadline)
- Won't deploy TRIBE v2 cloud (post-deadline)
- Won't add new platforms (Slack, Telegram) — five existing clients is plenty
- Won't refactor Mercury's core router (low ROI vs documentation work)

## Sources

- [Gemma 4 Good Hackathon — Kaggle](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
- [Mercury repo](https://github.com/AlexiosBluffMara/mercury)
- [Cortex repo](https://github.com/AlexiosBluffMara/cortex)
- See sibling docs: `HACKATHON_COSTS_2026-05-06.md`, `CLOUD_REPLICATION_2026-05-06.md`, `GEMMA4_UPDATE_2026-05-06.md`, `SELF_UPDATE_LOOP_2026-05-06.md`
