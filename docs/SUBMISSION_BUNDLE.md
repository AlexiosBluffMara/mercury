# Nous Hackathon — submission bundle

Ready-to-post copy. Tweet variants, multi-platform video specs (Twitter,
YouTube, TikTok, Instagram Reels, YouTube Shorts), Discord post + thread,
and a copyright-safe demo-content guide.

---

## 1. Tweets

All variants are emoji-free, under 280 chars, packed with the keywords X's
search index loves (`Hermes Agent`, `Kimi K2.6`, `RTX 5090`, `Nous Research`).

> If you want to quote-retweet a Nous Research hackathon post for engagement,
> open https://x.com/NousResearch and pick a recent hackathon-launch tweet
> from their pinned content yourself — the URL changes if Nous re-pins, so
> we're not hard-coding it here.

### A — receipts hook (best as a standalone)

> 22 dollars of Kimi K2.6 produced 14 commits in 75 minutes. Those commits became Mercury — a Hermes Agent fork running across an RTX 5090, a Mac Mini, and Cloud Run. Six clients. Four skill domains. One brain. The receipts are in the repo.
>
> @NousResearch @Kimi_Moonshot
> github.com/AlexiosBluffMara/mercury

(280 chars exactly.)

### B — outcome hook (best for non-technical timelines)

> Mercury is an AI assistant you talk to from Discord, iMessage, or your terminal. It runs on your own GPU. Built on Hermes Agent + Kimi K2.6 via Nous Portal. The whole thing took 75 minutes of K2.6 inference. The chart and 14 commits proving it are in the repo.
>
> @NousResearch @Kimi_Moonshot

### C — submission line (use as the quote-RT body if you find the right Nous tweet)

> Submitting Mercury for the Hermes Creative track. One Kimi K2.6 brain on Nous Portal drove an entire fork: 14 commits in 75 minutes, $22.04 of K2.6 spend, six client surfaces, four custom skill domains, three nodes, one RTX 5090 in Chicago.
>
> github.com/AlexiosBluffMara/mercury

### Tweet thread to follow whichever variant you posted (reply to your own tweet)

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

### Initial post (paste in main channel)

```
Mercury — Hermes Agent fork, multi-domain agent stack
Repo: https://github.com/AlexiosBluffMara/mercury
Showcase: https://alexiosbluffmara.github.io/mercury/
Demo: <PASTE TWEET URL>
Receipts: $22.04 of Kimi K2.6 spend, 14 commits in 75 minutes, full proof in kimi_proof/. Architecture, breakdown, and live brain-scan demo in the thread below.
```

### Thread replies (right-click your post → Create Thread → name it `Mercury submission details`)

| # | Image | Caption |
|---|---|---|
| 1 | `assets/architecture_v2.png` | Six clients fan into one Hermes Gateway, four custom skills, three nodes. Architecture v2, the version that actually shipped. |
| 2 | `assets/architecture_v1_deprecated.png` | What we changed: one brain instead of planner+coder split. Skill auto-load by context. Three-node mesh. Six surfaces instead of Discord-only. Cross-session memory. |
| 3 | `kimi_proof/06_nous_portal_usage_2026-04-30.png` | Kimi K2.6 receipts. Apr 28-29 spike maps 1:1 to a 75-minute burst that built the brain visualizer, the gateway, the four skill domains, and the docs. |
| 4 | (your screenshot of the brain viewer) | Live demo: 20-second video → TRIBE v2 surface BOLD prediction → Gemma narration. 369-second wall, 12 visual-cortex parcels lit up. Vanilla Three.js, no React. |
| 5 | (no image — text only) | One GPU, eviction-driven swap. gemma4:e4b for fast (10 GB, 194 tok/s), gemma4:26b for deep (19 GB, 184 tok/s), TRIBE v2 for scans (~22 GB, ~6 min). State machine in cortex/gpu_scheduler.py enforces the lock. |

---

## 3. Demo content — what to actually film

The video Mercury processes in your demo should NOT be a clip from any
commercial film, TV show, or copyrighted YouTube channel. Content ID will
flag it on Twitter, YouTube, TikTok, and Instagram regardless of how short
the clip is or whether you credit the rights-holder. Attribution does not
grant a license. Strikes can suspend the account you submit from.

### Use one of these instead — all are safe to upload to every platform

| Source | License | What you'd use | Attribution line |
|---|---|---|---|
| **`D:/cortex/assets/demo_clip_20s.mp4`** (already in your repo, scanned in this submission) | yours | 20s clip — primary recommendation | none required |
| Blender Open Movies — *Big Buck Bunny*, *Sintel*, *Tears of Steel*, *Spring*, *Charge* | CC-BY 4.0 | any 5–10 s segment of vivid action | "Excerpt from <Title> © Blender Foundation, CC-BY 4.0, https://www.blender.org/about/projects/" |
| **NASA imagery** — Earth-from-orbit, ISS, Mars rover footage | Public domain | any segment | "NASA, public domain" |
| **Pexels** (https://www.pexels.com/videos/) | Pexels License (free for any use, no attribution required) | any clip | optional credit to creator |
| **Pixabay** (https://pixabay.com/videos/) | Pixabay Content License | any clip | optional |
| **Internet Archive — Prelinger Archives, NASA, Library of Congress** | various, mostly public domain | any vintage / archival clip | per-item license noted on the page |
| **Google I/O keynotes, Google DeepMind / Gemma announcements** | YouTube standard license — short excerpts okay for criticism / commentary in a Google-sponsored hackathon context | 5–10 s | "Excerpt from <video title>, © Google, used under YouTube standard license" |

### How to grab a Blender Open Movie clip with ffmpeg

```bash
# 1. Download the source from the official Blender CDN (these are free and
#    explicitly redistributable under CC-BY).
curl -L -o D:/mercury/demo/sintel.mp4 \
  "https://download.blender.org/durian/movies/Sintel.2010.720p.mkv"

# 2. Pick a 6-second segment (use the 5:30-ish wide-shot, or any moment
#    you like — preview with VLC first, note timestamps).
#    Below: cut from 1:24 to 1:30. Adjust to taste.
ffmpeg -y -ss 00:01:24 -to 00:01:30 -i D:/mercury/demo/sintel.mp4 \
  -c:v libx264 -crf 18 -preset slow -c:a aac \
  D:/mercury/demo/sintel_excerpt_6s.mp4
```

Substitute `sintel.mp4` paths for any of: `BigBuckBunny.mp4`, `Spring.mp4`,
`TearsOfSteel.mp4`, `Charge.mp4`. All are at `https://download.blender.org/`
under their respective project subdirectories.

If you use a Blender clip in your demo, add this line to your YouTube
description and your tweet:

> Demo input excerpt: <Title> © Blender Foundation, CC-BY 4.0,
> https://studio.blender.org/films/

---

## 4. Master cut — record at 4K so we can re-export forever

### OBS settings for the master

Settings → Video:

- Base (Canvas) Resolution: **3840x2160**
- Output (Scaled) Resolution: **3840x2160**
- Common FPS Values: **60**

Settings → Output → Recording:

- Recording Path: `D:/mercury/demo`
- Recording Format: **MKV** (crash-safe; we convert to MP4 after)
- Recording Quality: **Indistinguishable Quality, Large File Size**
- Encoder: **NVIDIA NVENC HEVC** (hardware accel on the 5090, near-lossless at the highest preset)
- Rate Control: **CQP**, **CQ Level: 14**
- Keyframe Interval: **2 s**
- Preset: **P7 (slowest, best quality)**
- Profile: **main10**

The master file will be ~3-6 GB per minute. Disk is cheap; later content is
forever.

### Apple-commercial style script — 75 seconds, 9 cuts, no voiceover

Hold each beat **5-9 seconds**. Slow camera moves only. One typographic
overlay per cut, set in a clean sans (system default is fine). Black
background between cuts (1 frame is enough; gives the eye a beat).

| # | Time | What's on screen | On-screen text |
|---|---|---|---|
| 1 | 0:00 - 0:08 | Black. Fade up to a single line of text, centered. | `Mercury.` |
| 2 | 0:08 - 0:16 | Cut to architecture diagram. Slowly zoom 5%. | `One brain. Six clients. Three nodes.` |
| 3 | 0:16 - 0:25 | Cut to terminal: `nvidia-smi` showing 5090 idle. Hold. | `RTX 5090. Idle.` |
| 4 | 0:25 - 0:35 | Cut to Discord. Drop your demo clip into the bot's DM. Bot replies "scanning…". | `/scan demo_clip.mp4` |
| 5 | 0:35 - 0:50 | Split-screen: terminal showing scheduler `gemma_active → swapping → tribe_active`, alongside Task Manager → Performance → GPU 0 graph spiking. | `Gemma evicts. TRIBE v2 loads.` |
| 6 | 0:50 - 1:05 | Cut to brain viewer. 3D cortex animates to predicted BOLD activity. Click an ROI. Sidebar opens. | `Predicted cortical response. 12 visual ROIs.` |
| 7 | 1:05 - 1:13 | Cut to repo README. Scroll past the architecture, land on the Kimi receipts chart. Pause. | `Twenty-two dollars of Kimi K2.6.` |
| 8 | 1:13 - 1:18 | Cut to the chart, isolated. Hold on the spike. | `Seventy-five minutes. Fourteen commits.` |
| 9 | 1:18 - 1:25 | Black. Fade up: repo URL. | `github.com/AlexiosBluffMara/mercury` |

### Pretty TUI for the GPU panel — use the built-in Mercury dashboard

You already have `mercury dashboard --tui` (Mercury 0.2+). It gives you a
local web dashboard at `http://127.0.0.1:9119` with a Chat tab AND a
status panel. Use that **on camera** instead of a raw shell loop:

```bash
"D:/mercury/.venv/Scripts/python.exe" -m mercury_cli.main dashboard --tui
```

Open `http://127.0.0.1:9119` in a browser and use that as your "GPU
monitor" tile in the recording layout. It's drawn with proper typography
and looks like a product, not a dev console.

If you want the raw nvidia-smi loop instead (works in git-bash on Windows
where `watch` isn't installed):

```bash
while true; do
  clear
  nvidia-smi --query-gpu=name,memory.free,memory.used,utilization.gpu \
    --format=csv,noheader
  echo
  curl -s http://127.0.0.1:8765/api/health | \
    "C:/Users/soumi/cortex/.venv/Scripts/python.exe" -c \
    "import sys,json; d=json.load(sys.stdin); g=d['gpu']; q=d['queue']; print(f'scheduler: {g[\"state\"]:15s} | swaps: {g[\"swap_metrics\"][\"total_swaps\"]} | queue: {q[\"queue_depth\"]}')"
  sleep 1
done
```

---

## 5. Re-export the master to every platform

Run all of these from the same source MKV. They produce per-platform-spec
MP4s that pass each platform's automated checks.

```bash
cd D:/mercury/demo

# 0. Convert master MKV → master MP4 (lossless transcode for editing)
INPUT=$(ls -t *.mkv | head -1)
ffmpeg -y -i "$INPUT" -c copy mercury_master_4k.mkv
ffmpeg -y -i mercury_master_4k.mkv \
  -c:v libx265 -crf 14 -preset slow -tag:v hvc1 \
  -c:a aac -b:a 256k -movflags +faststart \
  mercury_master_4k.mp4
```

### YouTube (16:9 — keep 4K)

```bash
# 4K master is ideal for YouTube. No re-export needed; upload mercury_master_4k.mp4.
ls -lh mercury_master_4k.mp4
```

### YouTube Shorts + TikTok + Instagram Reels (vertical 9:16, ≤60s, 1080×1920)

All three accept the same vertical export. **One file, three uploads.**

```bash
ffmpeg -y -i mercury_master_4k.mp4 -t 60 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1" \
  -c:v libx264 -crf 19 -preset slow -profile:v high -level 4.1 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  mercury_vertical_60s.mp4
```

### Twitter / X native (16:9, ≤140s, ≤512MB, MP4 H.264)

```bash
ffmpeg -y -i mercury_master_4k.mp4 -t 90 \
  -vf "scale=1920:1080" \
  -c:v libx264 -crf 21 -preset slow -profile:v high -level 4.1 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart \
  mercury_twitter_1080p.mp4
```

### Instagram Feed (square, optional, ≤60s)

```bash
ffmpeg -y -i mercury_master_4k.mp4 -t 60 \
  -vf "crop=ih:ih,scale=1080:1080,setsar=1" \
  -c:v libx264 -crf 21 -c:a aac -b:a 160k \
  mercury_ig_square.mp4
```

### Result

After all four exports:

```
D:/mercury/demo/
├── mercury_master_4k.mp4      ← YouTube long-form, archival
├── mercury_twitter_1080p.mp4  ← Twitter/X
├── mercury_vertical_60s.mp4   ← TikTok + Reels + YouTube Shorts (one file, 3 uploads)
└── mercury_ig_square.mp4      ← Instagram Feed (optional)
```

---

## 6. Pre-flight checklist before posting

- [ ] Tag pushed: `git tag` shows `v0.2.0-nous-creative` and the GitHub
      release page renders at https://github.com/AlexiosBluffMara/mercury/releases/tag/v0.2.0-nous-creative
- [ ] All 3 PNGs render in repo: `assets/architecture_v2.png`,
      `assets/architecture_v1_deprecated.png`,
      `kimi_proof/06_nous_portal_usage_2026-04-30.png`
- [ ] Cortex repo (Gemma submission) has zero `kimi|moonshot|nous` matches in `scripts/backends.py`
- [ ] GitHub Pages live: https://alexiosbluffmara.github.io/mercury/
- [ ] Master 4K MP4 uploaded to YouTube as **Unlisted**, URL copied
- [ ] Twitter native 1080p MP4 ready
- [ ] Vertical 60s MP4 ready (one file → TikTok + Reels + Shorts)
- [ ] Demo input clip is yours OR a CC-BY / public-domain source — never a copyrighted commercial film/TV clip
