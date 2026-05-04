---
name: short-form-content
description: Produce vertical (9:16) short-form video for YouTube Shorts, Instagram Reels, TikTok, X, and LinkedIn. Use when the user asks to make a short, reel, TikTok, sizzle reel, teaser, or "clip the highlights." Builds on video-editing + screen-recording skills; output is always 1080×1920, 30–60s, with hook in the first 2s.
---

# Short-Form Content Skill

You produce 1080×1920, 30–60-second vertical videos optimised for the algorithmic feeds (Shorts, Reels, TikTok, X, LinkedIn). Vertical reframe + captions burned in + hook ≤2s + clear CTA in last 3 frames.

## Hard rules (non-negotiable)

1. **9:16 only.** 1080×1920 (Shorts/Reels/TikTok primary). 1920×1080 horizontal is a different format — that's the `video-editing` skill, not this one.
2. **Hook in ≤2 seconds.** First frame must answer "why should I keep watching." Open on motion, faces, or a bold caption. Static title cards = scroll-past.
3. **Captions always burned in** (sound-off viewing dominates). Use the styling from `video-editing` (Segoe UI Bold / Google Sans Bold, white on near-black box, cardinal-red underline accent). Position in lower-third, never under the bottom Reels/Shorts UI band (≥240 px from bottom).
4. **Length: 30–60 s** for evergreen, 15 s for a teaser, ≤90 s for explainer. Never break 90 s.
5. **CTA in the last 3 frames** — link to the demo, follow handle, or "more in comments." Don't bury it.

## Pipeline

```
raw long-form ─▶ pick best 30–60s ─▶ vertical reframe ─▶ caption burn ─▶ post
```

### Step 1 — Pick the highlight

Two paths:
- **Have a script/timeline JSON** (e.g. from `auto_demo_video.py`): the highlight is whatever event chain you flag as `kind: "title"` or `kind: "highlight"`. Trim to those windows.
- **Don't have a timeline**: use `whisper-large-v3` to transcribe, then ask Gemma 4 26b for the punchiest 60s window:
  ```bash
  ffmpeg -i in.mp4 -ar 16000 -ac 1 -c:a pcm_s16le audio.wav
  whisper audio.wav --model large-v3 --output_format json --word_timestamps True
  # then feed the JSON to Gemma to pick the best clip window
  ```

### Step 2 — Vertical reframe (1080×1920)

Three reframe modes, pick the right one:

#### A. Talking head / single subject
Auto-track the face and crop:
```bash
ffmpeg -i in.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:v h264_nvenc out.mp4
```

#### B. Screen capture / UI demo (default for Cortex demos)
Capture the most active region. For Cortex demo recordings, the UI lives in the centre of the 3840×1600 monitor. Use:
```bash
ffmpeg -i raw.mp4 -vf "crop=900:1600:1470:0,scale=1080:1920" \
  -c:v h264_nvenc -preset p4 -cq 23 vertical.mp4
```
That crops a 900×1600 column starting at x=1470 (centre-ish), scales to 1080×1920.

#### C. Blur-pad (preserves full frame, fills bars with blur)
```bash
ffmpeg -i in.mp4 -filter_complex "\
  [0:v]scale=1080:1920:force_original_aspect_ratio=increase,boxblur=24:6,crop=1080:1920[bg];\
  [0:v]scale=1080:-1[fg];\
  [bg][fg]overlay=(W-w)/2:(H-h)/2[v]" \
  -map "[v]" -map 0:a? -c:v h264_nvenc -preset p4 -cq 23 vertical.mp4
```

### Step 3 — Caption burn

If you already have a JSON timeline (see `D:/cortex/scripts/edit_demo_video.py`), feed it through after vertical reframe — set `MON_W=1080 MON_H=1920` in your post-process.

If captions come from Whisper word-timestamps:
```bash
# Convert Whisper JSON → SRT
whisper-srt audio.json > captions.srt
# Burn into vertical
ffmpeg -i vertical.mp4 -vf "subtitles=captions.srt:force_style='Fontname=Segoe UI Black,FontSize=24,PrimaryColour=&H00FFFFFF&,BackColour=&HC8141821&,Outline=2,Shadow=1,MarginV=180,Alignment=2'" \
  -c:v h264_nvenc -preset p4 -cq 23 captioned.mp4
```

### Step 4 — Hook + CTA bumpers

Use ffmpeg concat to prepend a 2s title card and append a 3s CTA:
```bash
# Make title card (cardinal red bg, big white text)
ffmpeg -y -f lavfi -i color=c=0xCC0000:s=1080x1920:r=30:d=2 \
  -vf "drawtext=fontfile='C\:/Windows/Fonts/segoeuib.ttf':text='Cortex sees the brain':\
fontsize=120:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
  -c:v h264_nvenc title.mp4

# Concat: title + body + CTA
printf "file 'title.mp4'\nfile 'captioned.mp4'\nfile 'cta.mp4'\n" > concat.txt
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy short.mp4
```

## Per-platform export

All sources start from `short.mp4` (1080×1920 H.264 AAC):

| Platform | Spec | Notes |
|---|---|---|
| YouTube Shorts | 1080×1920, ≤60s, mp4 | Title ≤100ch, #Shorts in description, vertical thumb 1080×1920 |
| Instagram Reels | 1080×1920, ≤90s | First 3 chars of caption are the visible hook on the feed |
| TikTok | 1080×1920, 9–60s recommended | Captions in TikTok-native style outperform burned-in for engagement, but burn in anyway for cross-post |
| X (Twitter) | 1080×1920 ≤140s, mp4 | Auto-captions are unreliable; always burn in |
| LinkedIn | 1080×1920 ≤90s, mp4 | Native upload outperforms YouTube link 5–10x in feed |
| Pinterest Idea Pin | 1080×1920 ≤60s | Use lighter design, less aggressive cuts |

Don't transcode for each platform if specs match — re-upload `short.mp4` directly. Re-encoding loses 1–2% quality each pass.

## Anti-patterns (kill on sight)

- ❌ Slow opens (intro music + logo for 5s before content) — kills retention.
- ❌ Captions in tiny font or behind UI overlay band.
- ❌ 4:3 or 16:9 source uploaded to a vertical platform — it gets letterboxed and looks unprofessional.
- ❌ Shaky / fast-pan vertical reframe of horizontal source — use blur-pad or fixed crop.
- ❌ "Wait for it…" baits — algorithm punishes high drop-off in the first 3 s. Lead with the payoff.
- ❌ Cross-posting WITH platform watermarks visible (TikTok logo on Instagram, etc.) — algorithms downrank.

## Cortex-specific shorts

For each demo recording, generate **3** variants:
1. **30s teaser** — TRIBE result + one persona narration. CTA: "full demo at big-apple.scylla-betta.ts.net"
2. **60s explainer** — upload → TRIBE running → 4 persona embeds in Discord. CTA: "code on github.com/AlexiosBluffMara/cortex"
3. **15s sizzle** — punchy cuts, brain spinning, ROI list flashing, narration scrolling. CTA: "what does YOUR brain say?"

Output to `D:/cortex/demo_videos/shorts/<unix-ts>_{teaser,explainer,sizzle}.mp4`.

## See also

- `video-editing` — base ffmpeg/moviepy recipes
- `screen-recording` — capturing source footage
- `livestreaming` — long-form streams that get clipped into shorts
- `adobe-for-creativity:adobe-edit-quick-cut` — Adobe's sizzle-reel skill (use for hand-curated highlights)
