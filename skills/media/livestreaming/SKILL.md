---
name: livestreaming
description: Configure and operate live streaming from Soumit's Seratonin desktop to Twitch, YouTube Live, X, LinkedIn Live, and multi-destination via Restream. Use when the user asks to "go live", "start a stream", set up an OBS scene, troubleshoot stream health, or run multi-destination simulcast. Prefers OBS Studio + obs-websocket for orchestration; ffmpeg-only fallback for headless RTMP push.
---

# Livestreaming Skill

Streams originate from the Seratonin desktop (RTX 5090 → NVENC → 1080p60 sustained without dropping frames). Use the 5090's hardware encoder for everything — never x264 software encode while live.

## Account snapshot

| Platform | Stream key location | Notes |
|---|---|---|
| Twitch  | `~/.streaming/twitch.key`  (gitignored) | dashboard.twitch.tv/u/<handle>/settings/stream |
| YouTube | `~/.streaming/youtube.key` (per-event)  | studio.youtube.com → Go Live → Stream key. Each scheduled event gets a fresh key. |
| X       | `~/.streaming/x.key`       (Twitter Producer) | producer.x.com — eligibility-gated |
| LinkedIn Live | OAuth via Restream      | Requires LinkedIn Live access (apply once) |
| Restream (multi) | `~/.streaming/restream.key` | Single OBS output → fans out to all platforms |

Always re-fetch the key from the dashboard before going live; YouTube rotates per scheduled event, others can be stable.

## Tool priority

| Tier | Tool | When |
|---|---|---|
| 1 | OBS Studio + obs-websocket | Default. Scenes, transitions, alerts, multiple sources, recording-while-streaming. |
| 2 | Streamlabs Desktop | Only if the user explicitly asks for it; OBS covers everything. |
| 3 | `ffmpeg` direct RTMP push | Headless / scripted streams (no UI), single source. |
| 4 | Restream Studio (browser) | Co-streams, guest interviews, picture-in-picture without local OBS. |

## OBS scene presets to keep ready

Stored as `.json` in `~/Documents/OBS Studio/basic/scenes/`:

1. **Standby** — looping logo + waiting-room music. Pre-stream/break scene.
2. **Demo** — primary monitor capture + cam in lower-right corner + Cortex chat overlay.
3. **Talking head** — webcam fullscreen, Twitch chat on right, Spotify now-playing in upper-right.
4. **Co-stream** — split screen via NDI / Restream input, our cam on left.
5. **BRB** — animated "be right back" card.

Per scene, set: NVENC H.264, 1080p60, CBR 6500 kbps (Twitch cap) or 9000 kbps (YouTube/Restream), keyframe interval 2 s, AAC 160 kbps stereo.

## OBS WebSocket orchestration

Built into OBS since v28; enable in Tools → WebSocket Server. Default port 4455.

```bash
uv pip install obsws-python
```

```python
from obsws_python import ReqClient
cl = ReqClient(host="localhost", port=4455, password="<from-OBS-settings>")

# Scene management
cl.set_current_program_scene("Standby")
cl.set_current_program_scene("Demo")

# Transitions
cl.set_current_scene_transition("Stinger")
cl.trigger_studio_mode_transition()

# Streaming control
status = cl.get_stream_status()        # GetStreamStatus
cl.start_stream()
cl.stop_stream()

# Recording (concurrent with stream)
cl.start_record()
cl.stop_record()
```

## ffmpeg direct RTMP (headless)

When OBS is overkill — e.g. you just want to push a desktop capture to Twitch without scenes/alerts:

```bash
TWITCH_KEY=$(cat ~/.streaming/twitch.key)
ffmpeg -y \
  -f gdigrab -framerate 60 -offset_x 0 -offset_y 0 -video_size 3840x1600 -i desktop \
  -f dshow -i audio="virtual-audio-capturer" \
  -c:v h264_nvenc -preset p4 -profile:v high -rc cbr -b:v 6500k -maxrate 6500k -bufsize 13000k \
  -g 120 -keyint_min 60 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 \
  -f flv "rtmp://live.twitch.tv/app/$TWITCH_KEY"
```

YouTube Live RTMP endpoint: `rtmp://a.rtmp.youtube.com/live2/<key>`.

For multi-destination without paying for Restream, push to two RTMP endpoints in parallel:

```bash
ffmpeg -y -f gdigrab -framerate 60 -i desktop -f dshow -i audio="virtual-audio-capturer" \
  -c:v h264_nvenc -preset p4 -rc cbr -b:v 6500k -maxrate 6500k -bufsize 13000k -g 120 -pix_fmt yuv420p \
  -c:a aac -b:a 160k \
  -f tee -map 0:v -map 1:a "[f=flv]rtmp://live.twitch.tv/app/$TWITCH_KEY|[f=flv]rtmp://a.rtmp.youtube.com/live2/$YT_KEY"
```

5090 NVENC handles two parallel encodes trivially.

## Pre-stream checklist (run before every Go Live)

1. **Key freshness** — `cat ~/.streaming/<platform>.key` and verify it matches the dashboard.
2. **Bitrate budget** — `speedtest-cli` upstream ≥ 2× target bitrate. Twitch 6.5 Mbps → need 13 Mbps up.
3. **NVENC available** — `ffmpeg -hide_banner -encoders 2>&1 | grep nvenc` (must list `h264_nvenc`).
4. **GPU headroom** — `nvidia-smi`: 5090 should show <50% util before stream. If TRIBE / cortex Ollama is hot, decide whether to evict.
5. **Audio routing** — `Get-AudioDevice -List | Where-Object Default` (PowerShell) — confirm capture device is the right one. If using Discord call audio, use VoiceMeeter to bus-route.
6. **Scene preview** — flip to each scene in OBS Studio Mode and check sources are alive (no "missing source" red icons).
7. **Latency mode** — Twitch low-latency on for chat-interactive streams; off for replay quality. YouTube ultra-low-latency for Q&A.
8. **Recording** — always toggle local recording ON in addition to streaming. NVENC has the headroom; gives you a clean source for clips later.
9. **Chat overlay** — alerts widget url in browser source (StreamElements / StreamLabs). Test alert sound.
10. **Internet failover** — if TRIBE/cortex is running on the same upstream link, expect contention. Throttle Ollama via `OLLAMA_KEEP_ALIVE=5m` during the stream.

## Stream health monitoring

While live, watch:

```python
import time
from obsws_python import ReqClient
cl = ReqClient(host="localhost", port=4455, password="...")
while True:
    s = cl.get_stream_status()
    print(f"frames={s.output_total_frames} skipped={s.output_skipped_frames} "
          f"congestion={s.output_congestion:.2%} bytes={s.output_bytes}")
    time.sleep(5)
```

Skip rate >2% over a 30s window = problem (CPU/GPU saturated, network drop, or sustained framerate over what NVENC can handle at this bitrate). Drop bitrate or framerate before the audience notices buffering.

## Replay → clips pipeline

The local recording captured during the stream goes to `~/Videos/OBS/`. Pipe it through:

1. **`screen-recording` skill** — already captured by OBS, no need to re-grab.
2. **`video-editing` skill** — trim highlights, add chapter markers, transcode to delivery codec.
3. **`short-form-content` skill** — vertical reframe of best moments → Reels/Shorts/TikTok.

For Cortex demos specifically: every TRIBE scan during a stream becomes a 30–60s short. The `D:/cortex/scripts/auto_demo_video.py` orchestrator already produces a timeline JSON; pair it with the OBS recording timestamp to extract precisely the demo window.

## Anti-patterns

- ❌ x264 software encode while streaming + running TRIBE — 5090 sits idle while CPU melts.
- ❌ Streaming at 1080p60 4500 kbps on Twitch — the platform caps bitrate but lets you waste bandwidth; use 6500 kbps and stop there.
- ❌ Forgetting to kill the local Ollama keep-alive — model stays in VRAM during the entire stream when it's only needed for the demo segment.
- ❌ Streaming the whole 7680×1600 multi-monitor setup — viewers see a tiny demo on a sea of Discord/IDE. Capture only the relevant monitor or window.
- ❌ Using browser source for chat overlay without disabling Hardware Acceleration in the Twitch chat extension — causes invisible-text bug on NVIDIA drivers.
- ❌ Going live without a local recording — if the stream drops and you couldn't clip the moment from the platform, you've lost it forever.

## Going-live commands (one-shot)

```bash
# Standalone Twitch with current desktop:
~/.streaming/go-live.ps1 twitch demo

# Multi-destination (Twitch + YouTube simultaneously):
~/.streaming/go-live.ps1 multi demo
```

(The `go-live.ps1` script doesn't exist yet — write it under `D:/cortex/scripts/streaming/` when first asked. It should source key files, validate prereqs, then spawn ffmpeg with the right command from this skill.)
