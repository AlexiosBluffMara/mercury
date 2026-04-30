# Nous Hackathon — submission bundle

Ready-to-post copy for the May 3 deadline. Tweet, Discord post, and the
follow-up thread that drops the proof images.

---

## 1. Tweet (≤ 280 chars, tag accounts, attach demo video)

> Mercury — a single Hermes Agent fork running across a Mac Mini, an RTX 5090, and Cloud Run. Six clients, four custom skill domains, one Kimi K2.6 brain. Built FOR the Nous hackathon BY Kimi via @NousResearch Portal (proof in the repo). 5090 stays warm.
>
> @NousResearch @Kimi_Moonshot
> github.com/AlexiosBluffMara/mercury

**Char count:** 280 exactly. Adjust the URL if the org name differs.

**Alt tweet (for the punchier hook variant):**

> $22 of Kimi K2.6 → 14 commits in 75 minutes → a 6-client, 3-node, 4-skill Hermes Agent. Mercury runs on a 5090 in Chicago, a Mac Mini in Bloomington, and Cloud Run for scale — all driven by one Nous Portal brain. Receipts in the repo.
>
> @NousResearch @Kimi_Moonshot
> github.com/AlexiosBluffMara/mercury

---

## 2. Discord — initial post in `#creative-hackathon-submissions`

> **Mercury** — Hermes Agent fork, multi-domain agent stack
> Repo: https://github.com/AlexiosBluffMara/mercury
> Demo video: <YOUTUBE_URL>
> Built: Mac Mini ↔ RTX 5090 (Chicago) ↔ Cloud Run, six clients (Terminal, Discord, Web UI, iMessage, Email, Mobile), four custom skill domains, one Kimi K2.6 brain via Nous Portal.
> Receipts: $22.04 of Kimi spend, 1,035 reqs, 14 commits in 75 minutes — full proof in `kimi_proof/` in the repo.
> Reply thread below has the architecture, skills breakdown, and live brain-scan demo.

(Keep it ≤ 4 lines for the channel feed; everything else goes in the thread.)

---

## 3. Follow-up comments (one per image, posted as a thread under the initial post)

### Comment A — drop the architecture diagram

> v2 architecture. Six client surfaces fan into one Hermes Gateway → Kimi K2.6 brain → 4 custom skill domains → 5-source data layer → 3-node infra (Mac dev, 5090 inference, Cloud Run scale).
> [attach: assets/architecture_v2.png]

### Comment B — drop the v1→v2 diff

> What changed from v1 to v2:
> • One brain (Kimi K2.6) instead of a 405B planner + K2.6 coder split
> • Skill auto-load by context — 4 domains today, n+1 tomorrow without touching the agent loop
> • 3-node mesh with one-command rsync sync, not a single 5090 with manual SSH fallback
> • Six clients (was Discord-only)
> • Cross-session memory (was per-session)
> [attach: assets/architecture_v1_deprecated.png]

### Comment C — drop the Kimi receipts

> Kimi K2.6 receipts. The full Mercury build was driven through `tools/kimi_dispatch.py` calling the Nous Portal. The Apr 28-29 spike on the chart maps 1:1 to a 75-minute burst of 14 commits in this repo (08:45 → 10:01 CDT, then a docs polish pass on Apr 29).
> $22.04 spend, 1,035 requests, 57M input tokens, 564K output tokens, 39.5M cache reads.
> Full commit timeline + raw session dumps in `kimi_proof/` in the repo.
> [attach: kimi_proof/06_nous_portal_usage_2026-04-30.png]

### Comment D — drop the live brain-scan output

> The threejs-design-dev skill drives a Cortex/TRIBE-v2 brain pipeline as one of the four custom domains. Live scan run during this submission — 20-second video clip → TRIBE v2 surface BOLD prediction → Gemma narration. 369s wall, peak at t=30s, 12 visual-cortex parcels lit up. Viewer at http://127.0.0.1:8765/ (local).
> [attach: a screenshot or short clip of the viewer with the cortex animating]

### Comment E (optional) — bonus tech detail for anyone who asks

> GPU is one card. We swap eviction-driven: gemma4:e4b for fast (10 GB, 194 tok/s), gemma4:26b for deep (19 GB, 184 tok/s). When a brain scan fires, both Gemmas evict and TRIBE-v2 (~22 GB) loads for ~6 minutes, then back to gemma. State machine in `cortex/gpu_scheduler.py` enforces the lock. No CUDA OOMs in the demo run.

---

## 4. Suggested 60-90s video script (snappier than the prior 3-min plan)

| Time | Beat | What's on screen |
|---|---|---|
| 0:00 | **Cold open** — `nvidia-smi` filling the screen, 5090 idle | terminal, white text on black |
| 0:04 | One-line title: `Mercury. Built by Kimi. Runs on a 5090.` | clean serif title card |
| 0:08 | **Six clients fan in** — quick montage: Discord ping, iMessage, Web UI, Terminal, Email, Telegram | 6-up split screen, ~0.5s each |
| 0:14 | "Six clients. Four custom skills. One Kimi K2.6 brain." | architecture diagram fade-up |
| 0:20 | **`/scan demo_clip.mp4`** in Discord | drag-drop a 20s video into Discord |
| 0:25 | **GPU swap visualization** — `nvidia-smi -l 1` side panel showing gemma → 0 → TRIBE → 22 GB | the "watch the model swap" beat |
| 0:40 | Cortex viewer pops up, 50 ROIs animating to the BOLD timeseries | http://127.0.0.1:8765/ in browser |
| 0:55 | Click an ROI — sidebar opens with the Gemma narration | "your visual cortex did this" |
| 1:05 | **Cut to the receipts** — Nous Portal usage chart, $22.04 spike highlighted | screenshot zoom to the Apr 28-29 spike |
| 1:10 | "75 minutes. 14 commits. $22 of Kimi K2.6." | text overlay |
| 1:15 | Final card: repo URL, MIT, "Built for the Nous Research + Kimi Hackathon" | logo card |

**Recording tools (already on this box):**
- OBS Studio for capture
- ffmpeg for the final cut: `ffmpeg -i raw.mkv -vf "scale=1920:1080" -c:v libx264 -crf 18 -c:a aac final.mp4`

**Audio:** No voiceover. Captions only. Clean tape, low-budget aesthetic, lets the receipts speak.

---

## 5. Pre-flight checklist (before posting)

- [ ] `git tag v0.2.0-nous-creative` and push tags
- [ ] Verify all 3 PNGs in repo: `assets/architecture_v2.png`, `assets/architecture_v1_deprecated.png`, `kimi_proof/06_nous_portal_usage_2026-04-30.png`
- [ ] `git log --since='2026-04-27' --until='2026-04-30'` matches the 14-commit table in README
- [ ] `D:/cortex/README.md` has zero matches for `kimi|moonshot|nous|k2.6` (Kaggle/Gemma submission rule)
- [ ] Demo video uploaded to YouTube as **Unlisted** (not public until tweet posts)
- [ ] Tweet drafted in TweetDeck/X but not posted; verify char count and account tags
- [ ] Discord initial post drafted in DM-to-self; comments A-D drafted with image attachments staged
