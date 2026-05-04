---
name: screen-recording
description: Capture the desktop, a single monitor, a window region, or a webcam on Soumit's Windows desktop. Use when the user asks to record a demo, capture a screencast, grab a region for a GIF, or set up timed/triggered captures. Default to ffmpeg gdigrab; reach for OBS for multi-source/scene captures and Windows Game Bar (Win+G) for clip-now scenarios.
---

# Screen Recording Skill

Soumit's Seratonin desktop has 2 monitors:
- **DISPLAY2 (primary)** — 3840×1600 at offset (0, 0)
- **DISPLAY1**  — 2560×1440 at offset (-3840, -550)

Always confirm geometry before capturing — `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens` from PowerShell prints them.

## Tool priority

| Tier | Tool | Best for |
|---|---|---|
| 1 | `ffmpeg -f gdigrab` | Headless / scripted capture, single monitor, timed recordings, anything orchestrated by Python. |
| 2 | OBS Studio (`obs-cli` or scenes) | Multi-source: cam + screen + audio + scenes. Start/stop via WebSocket. Best when you want polished output. |
| 3 | Windows Game Bar (Win+G) | Quick "clip the last 30 s" — handy but no scripting. |
| — | ShareX, Snagit, etc. | Avoid — none installed; ffmpeg + OBS cover everything. |

## ffmpeg gdigrab recipes

### Primary monitor (3840×1600 @ 30fps, NVENC)

```bash
ffmpeg -y -f gdigrab -framerate 30 \
  -offset_x 0 -offset_y 0 -video_size 3840x1600 \
  -i desktop \
  -c:v h264_nvenc -preset p4 -cq 23 -pix_fmt yuv420p \
  out.mp4
```

Use `-c:v libx264 -preset ultrafast` only if NVENC is busy (e.g. driving the inference router).

### Region of primary (e.g. browser at 800,200 1600x900)

```bash
ffmpeg -y -f gdigrab -framerate 30 \
  -offset_x 800 -offset_y 200 -video_size 1600x900 \
  -i desktop -c:v h264_nvenc -cq 23 region.mp4
```

### Specific window by title (no geometry hunting)

```bash
ffmpeg -y -f gdigrab -framerate 30 -i title="Cortex - Brain-response analysis" \
  -c:v h264_nvenc -cq 23 cortex_window.mp4
```

### With audio (system loopback via WASAPI dshow)

```bash
ffmpeg -y -f gdigrab -framerate 30 -i desktop \
  -f dshow -i audio="virtual-audio-capturer" \
  -c:v h264_nvenc -c:a aac -b:a 192k out_with_audio.mp4
```

`virtual-audio-capturer` requires the screen-capturer-recorder package; if missing, list devices with `ffmpeg -list_devices true -f dshow -i dummy`.

### Webcam (Logitech Brio etc.)

```bash
ffmpeg -y -f dshow -framerate 30 -video_size 1920x1080 \
  -i video="Logitech BRIO" -c:v h264_nvenc out_cam.mp4
```

## Picture-in-picture (screen + cam overlay)

```bash
ffmpeg -y \
  -f gdigrab -framerate 30 -i desktop \
  -f dshow -framerate 30 -video_size 640x360 -i video="Logitech BRIO" \
  -filter_complex "[1:v]scale=480:270[cam];[0:v][cam]overlay=W-w-32:H-h-32" \
  -c:v h264_nvenc -cq 23 pip.mp4
```

## OBS path (when ffmpeg isn't enough)

OBS lives at `C:/Program Files/obs-studio/bin/64bit/obs64.exe`. The WebSocket plugin (built-in since v28) listens on port 4455 with the password set in OBS → Tools → WebSocket Server Settings.

Drive it from Python with `obsws-python`:

```bash
uv pip install obsws-python
```

```python
from obsws_python import ReqClient
cl = ReqClient(host="localhost", port=4455, password="<set-in-obs>")
cl.set_current_program_scene("Demo")
cl.start_record()
# ... do stuff ...
cl.stop_record()
```

OBS scene presets to keep in `~/Documents/OBS Studio Profiles/Cortex/`:
- **Talking head** — webcam fullscreen + overlay logo
- **Demo** — primary monitor + small webcam PIP
- **Co-stream** — split screen, ours + guest

## Orchestrated end-to-end captures

For "record a workflow while a Python script drives it" pattern, see `D:/cortex/scripts/auto_demo_video.py`. The shape is:

1. Spawn `ffmpeg gdigrab` as a subprocess with stdin pipe.
2. Drive the workflow (browser via Patchright/CDP, API calls, etc.) — capture timestamped events into a JSON timeline.
3. Send `q\n` to ffmpeg's stdin to stop cleanly.
4. Post-process with `D:/cortex/scripts/edit_demo_video.py raw.mp4 timeline.json` to apply captions and speed up dead time.

## Troubleshooting

- **Black frames** — happens when capturing a hardware-accelerated overlay (some games, some video players). Disable hardware acceleration in the source app, or use `-f ddagrab` (DirectX desktop duplication, faster + handles HW overlays):
  ```bash
  ffmpeg -y -f ddagrab -framerate 30 -i desktop -vf hwdownload,format=bgra,format=yuv420p -c:v h264_nvenc out.mp4
  ```
- **Cursor not captured** — add `-draw_mouse 1` (default in gdigrab is on; check it wasn't overridden).
- **Choppy / dropped frames** — drop framerate to 24 or 30, or lower CRF/CQ.
- **File grows huge** — switch to `-c:v hevc_nvenc -cq 26 -tag:v hvc1` for ~half the size at same quality.

## Anti-patterns

- ❌ Recording both monitors at 7680×1600 30fps for hours — bloats files. Crop to one monitor or one window.
- ❌ Forgetting to send `q` — kill -9 on ffmpeg corrupts the moov atom. Always graceful-stop.
- ❌ Using OBS as a daemon when ffmpeg gdigrab covers the case — OBS in headless mode wastes ~500 MB RAM idle.
