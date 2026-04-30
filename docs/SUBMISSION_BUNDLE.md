# Nous Hackathon — submission bundle

Ready-to-post copy. Tweet variants, multi-platform video specs,
Discord post + thread.

---

## 1. Tweets — pick one

All variants are emoji-free, under 280 chars, packed with the keywords X's
search index loves (`Hermes Agent`, `Kimi K2.6`, `RTX 5090`, `Nous Research`,
`Moonshot AI`).

### A — quote-retweet of the hackathon launch (highest engagement)

Go to https://x.com/NousResearch/status/2039740198259462370
Click the retweet icon → **Quote**. Paste:

> Submitting Mercury for the Hermes Creative track. One Kimi K2.6 brain on Nous Portal drove an entire fork: 14 commits in 75 minutes, $22.04 of K2.6 spend, six client surfaces, four custom skill domains, three nodes, one RTX 5090 in Chicago.
>
> github.com/AlexiosBluffMara/mercury

(279 chars. The hackathon tweet shows under it. Judges tracking submissions through replies see this immediately.)

### B — receipts hook (best as a standalone)

> 22 dollars of Kimi K2.6 produced 14 commits in 75 minutes. Those commits became Mercury — a Hermes Agent fork running across an RTX 5090, a Mac Mini, and Cloud Run. Six clients. Four skill domains. One brain. The receipts are in the repo.
>
> @NousResearch @Kimi_Moonshot
> github.com/AlexiosBluffMara/mercury

(280 chars exactly.)

### C — outcome hook (best for non-technical timelines)

> Mercury is an AI assistant you talk to from Discord, iMessage, or your terminal. It runs on your own GPU. Built on Hermes Agent + Kimi K2.6 via Nous Portal. The whole thing took 75 minutes of K2.6 inference. The chart and 14 commits proving it are in the repo.
>
> @NousResearch @Kimi_Moonshot

(280 chars. Skip the URL line and let the auto-card embed do the work.)

### Tweet thread to follow whichever variant you posted

Reply to your own tweet, twice:

**Reply 1 — receipts:**
> The Apr 28-29 spike on this chart is one Kimi K2.6 session that built the Mercury fork: skills, dispatcher fixes, the Three.js viewer, the gateway wiring, the docs. Full per-commit timeline in kimi_proof/ in the repo.
>
> [attach: kimi_proof/06_nous_portal_usage_2026-04-30.png]

**Reply 2 — architecture:**
> v2 architecture. Mac Mini in Bloomington for skill authoring, RTX 5090 in Chicago for inference, Google Cloud Run as managed scale fallback. Six clients fan in, one Kimi K2.6 brain fans out.
>
> [attach: assets/architecture_v2.png]

---

## 2. Discord — `#creative-hackathon-submissions`

### Initial post (4 lines, paste in main channel)

```
Mercury — Hermes Agent fork, multi-domain agent stack
Repo: https://github.com/AlexiosBluffMara/mercury
Demo: <PASTE TWEET URL>
Receipts: $22.04 of Kimi K2.6 spend, 14 commits in 75 minutes, full proof in kimi_proof/. Architecture, breakdown, and live brain-scan demo in the thread below.
```

### Thread replies (right-click your post → Create Thread → name it `Mercury submission details`)

| # | Image | Caption |
|---|---|---|
| 1 | `assets/architecture_v2.png` | Six clients fan into one Hermes Gateway, four custom skills, three nodes. Architecture v2, the version that actually shipped. |
| 2 | `assets/architecture_v1_deprecated.png` | What we changed: one brain instead of planner+coder split. Skill auto-load by context. Three-node mesh. Six surfaces instead of Discord-only. Cross-session memory. |
| 3 | `kimi_proof/06_nous_portal_usage_2026-04-30.png` | Kimi K2.6 receipts. Apr 28-29 spike maps 1:1 to a 75-minute burst that built the brain visualizer, the gateway, the skills, and the docs. |
| 4 | (screenshot of the brain viewer) | Live demo: 20 second video → TRIBE v2 surface BOLD prediction → Gemma narration. 369 second wall, 12 visual-cortex parcels lit up. Vanilla Three.js, no React. |
| 5 | (no image — text only) | One GPU, eviction-driven swap. gemma4:e4b for fast (10 GB, 194 tok/s), gemma4:26b for deep (19 GB, 184 tok/s), TRIBE v2 for scans (~22 GB, ~6 min). State machine in cortex/gpu_scheduler.py enforces the lock. No CUDA OOMs in the run. |

---

## 3. Video — produce one master, then re-export per platform

### Master cut

Record at **1920x1080, 30 fps, ~75-90 seconds**. That's the source-of-truth file. Everything else is a re-export.

### Platform exports from the master

| Platform | Spec | Command |
|---|---|---|
| **YouTube** | use the master as-is (16:9, ≤4 GB, ≤12 hr) | upload `mercury_demo.mp4` directly |
| **Twitter / X (in-feed video)** | ≤140 sec, ≤512 MB, MP4 H.264 + AAC, max 1920x1200 | `ffmpeg -i mercury_demo.mp4 -t 90 -c:v libx264 -crf 23 -preset slow -c:a aac -b:a 128k -movflags +faststart mercury_twitter.mp4` |
| **Instagram Reels** (vertical) | 9:16, ≤90 sec, ≤4 GB, 1080×1920 | `ffmpeg -i mercury_demo.mp4 -t 90 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" -c:v libx264 -crf 22 -c:a aac -b:a 128k mercury_reel.mp4` |
| **Instagram Feed** (square) | 1:1, ≤60 sec, 1080×1080 | `ffmpeg -i mercury_demo.mp4 -t 60 -vf "crop=ih:ih,scale=1080:1080" -c:v libx264 -crf 23 -c:a aac mercury_ig_square.mp4` |

You don't need all four. The pragmatic minimum is **YouTube + Twitter native + Instagram Reels** (Reels gets you the algorithmic boost; the square feed version is optional).

### Recording script — 75-90 seconds, no voiceover, captions only

| Time | What's on screen | Caption to overlay |
|---|---|---|
| 0:00 - 0:04 | Terminal: `nvidia-smi` showing the 5090, idle | `RTX 5090. Idle.` |
| 0:04 - 0:10 | Title card | `Mercury — Hermes Agent fork. Built by Kimi K2.6.` |
| 0:10 - 0:18 | Architecture diagram (zoom slowly) | `One brain. Six clients. Three nodes.` |
| 0:18 - 0:25 | Discord: drop `D:/cortex/assets/demo_clip_20s.mp4` into the bot's DM | `/scan demo_clip.mp4` |
| 0:25 - 0:40 | Side-by-side: viewer loading + GPU monitor showing swap (gemma evicts, TRIBE loads) | `Gemma evicted. TRIBE v2 loads. 22 GB.` |
| 0:40 - 0:60 | Brain viewer: 3D cortex, time scrubber animating, ROIs lighting up | `Surface BOLD. 12 visual ROIs. Peak at 15s.` |
| 0:60 - 0:75 | Switch to repo: scroll past architecture, land on Kimi receipts chart | `$22.04 of Kimi K2.6.` |
| 0:75 - 0:85 | Outro card | `github.com/AlexiosBluffMara/mercury` |

### What to use to record

- **OBS Studio** (free, https://obsproject.com/) — for the screen recording itself.
- **DaVinci Resolve** (free, https://www.blackmagicdesign.com/products/davinciresolve) — for editing if you want title cards / captions.
- **ffmpeg** — for the platform re-exports above.
- (Optional) **Task Manager → Performance tab → GPU 0** — if you want a recognizable-to-laypeople UI showing the GPU spike. Useful for the Instagram cut where viewers won't know what `nvidia-smi` is.

---

## 4. Pre-flight checklist before posting

- [ ] Tag pushed: `git tag` shows `v0.2.0-nous-creative` and it's at https://github.com/AlexiosBluffMara/mercury/releases/tag/v0.2.0-nous-creative
- [ ] All 3 PNGs render in repo: `assets/architecture_v2.png`, `assets/architecture_v1_deprecated.png`, `kimi_proof/06_nous_portal_usage_2026-04-30.png`
- [ ] Cortex repo (Gemma submission) has zero `kimi|moonshot|nous` matches in `scripts/backends.py`
- [ ] Master video uploaded to YouTube as **Unlisted** — copy the URL
- [ ] Twitter native MP4 (`mercury_twitter.mp4`) ready to attach
- [ ] Instagram Reel (`mercury_reel.mp4`) ready
