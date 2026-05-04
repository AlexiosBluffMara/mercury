---
name: video-editing
description: Programmatic video editing for Soumit's machine (Windows + RTX 5090). Use when the user asks to cut, splice, speed up, add captions/lower-thirds, color-correct, or stitch clips. Default to ffmpeg with NVENC; fall through to moviepy when frame-level Python logic is needed; reach for DaVinci Resolve only for hand-edited finishing.
---

# Video Editing Skill

You are operating as the editor on Soumit's RTX 5090 desktop. The 5090 has full NVENC + NVDEC, so encode everything with `h264_nvenc` (and `hevc_nvenc` for HEVC) unless the destination explicitly demands x264. CPU encoding is a bug, not a fallback.

## Tooling priority

| Tier | Tool | When to use |
|---|---|---|
| 1 | `ffmpeg` (filter_complex + NVENC/NVDEC) | 95% of jobs — trim, concat, speed, scale, captions, overlays, audio mux, transcode |
| 2 | `moviepy` (Python) | When the edit needs frame-level Python logic, complex compositing, or per-event programmatic overlays. Slow — uses x264 in software. |
| 3 | DaVinci Resolve (UI) | Last resort: hand-color-graded finishing, hero shots, audio sweetening. Don't reach here for batch/pipeline work. |
| — | Premiere / Final Cut | Avoid — neither is installed and Resolve is more capable for free. |

`ffmpeg` is at `C:/Users/soumi/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_*/ffmpeg-*-full_build/bin/ffmpeg.exe` and on PATH as `ffmpeg`.
`moviepy 2.1.x` lives in `C:/Users/soumi/cortex/.venv`. Python 3.12.

## Standard recipes

### 1. Concat clips (no re-encode)

```bash
# clips.txt: file 'clip1.mp4'\nfile 'clip2.mp4'\n…
ffmpeg -y -f concat -safe 0 -i clips.txt -c copy out.mp4
```

If the clips have different codecs/containers, drop `-c copy` and let it transcode (with `-c:v h264_nvenc -preset p4`).

### 2. Trim without re-encoding (cuts on keyframes only)

```bash
ffmpeg -y -ss 00:01:23 -to 00:02:45 -i in.mp4 -c copy out.mp4
```

### 3. Frame-accurate trim (re-encode)

```bash
ffmpeg -y -i in.mp4 -ss 00:01:23.500 -to 00:02:45.250 \
  -c:v h264_nvenc -preset p4 -cq 21 -c:a aac -b:a 192k out.mp4
```

### 4. Speed up dead time (e.g. compress 5-min build into 30 s)

```bash
# 10x speed
ffmpeg -y -i in.mp4 -filter:v "setpts=PTS/10" -an out.mp4
```

For multi-segment speedups (1x for highlights, 10x for waits), build a `filter_complex` with `split → trim → setpts → concat` — see `D:/cortex/scripts/edit_demo_video.py` for a working template.

### 5. Captions / lower-thirds via drawtext

```bash
ffmpeg -y -i in.mp4 -vf "drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':\
text='Hello world':fontsize=56:fontcolor=white:bordercolor=black@0.85:borderw=4:\
box=1:boxcolor=0x141821@0.85:boxborderw=24:\
x=(w-text_w)/2:y=h-220" -c:v h264_nvenc out.mp4
```

Brand colors: cardinal red `0xCC0000`, near-black panel `0x141821`. Don't use yellow boxes on screen captures unless you can verify the coordinates land on the actual element — random-looking highlights are worse than no highlights.

### 6. Burn timed captions from a JSON timeline (script)

Use `D:/cortex/scripts/edit_demo_video.py <raw.mp4> <timeline.json>` — it speeds up wait segments, draws captions in the bottom band, encodes via NVENC. Edit the script's `font_candidates` / `CAPTION_*` block to retheme.

### 7. Vertical reframe (1080×1920 for shorts)

```bash
ffmpeg -y -i in.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" \
  -c:v h264_nvenc -preset p4 -cq 21 out_vertical.mp4
```

For better framing, blur-pad instead of crop:
```bash
ffmpeg -y -i in.mp4 -filter_complex "\
  [0:v]scale=1080:1920:force_original_aspect_ratio=increase,boxblur=20:5[bg];\
  [0:v]scale=1080:-1[fg];\
  [bg][fg]overlay=(W-w)/2:(H-h)/2[out]" \
  -map "[out]" -c:v h264_nvenc out_vertical.mp4
```

### 8. Mux/replace audio

```bash
# Replace audio
ffmpeg -y -i video.mp4 -i music.mp3 -map 0:v -map 1:a -c:v copy -shortest out.mp4

# Sidechain duck music under voiceover
ffmpeg -y -i video.mp4 -i music.mp3 -filter_complex \
  "[1:a][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=80:release=400[music];\
   [0:a][music]amix=inputs=2[a]" \
  -map 0:v -map "[a]" -c:v copy out.mp4
```

### 9. Hardware-accelerated transcode (5090)

```bash
ffmpeg -y -hwaccel cuda -hwaccel_output_format cuda \
  -i in.mov -c:v h264_nvenc -preset p4 -cq 21 -c:a aac out.mp4
```

For batch jobs, NVENC saturates well past 4 concurrent encodes on the 5090.

## Generation-side helpers

- **Manim** — `D:/mercury/skills/creative/manim-video` for math/diagram animations. Renders to mp4.
- **ASCII video** — `D:/mercury/skills/creative/ascii-video` for terminal aesthetic.
- **Brain viz** — `D:/mercury/skills/creative/brain-viz` (3D fmri renders).

## Anti-patterns (don't do)

- ❌ Using x264 software encode by default — always NVENC on this machine.
- ❌ Concat with mismatched codecs and `-c copy` — produces glitchy joins; transcode instead.
- ❌ Drawing bounding boxes onto a screen-capture feed without verifying the coords land on the actual element. Use captions instead, or capture per-element bounding boxes from the page DOM and remap them.
- ❌ Burning captions with PIL+`writebands` then concatenating — moviepy in software is 10–30 min per minute of 4K. Always prefer ffmpeg drawtext.
- ❌ Re-rendering when you only need to remux — `-c copy` is your friend for chapters/trim/concat.

## Output conventions

- Project videos land in `D:/cortex/demo_videos/` and `D:/mercury/out/videos/`.
- Filenames: `<project>_<purpose>_<unix-ts>.mp4`. Don't overwrite existing finals — always new timestamp.
- Default container: `.mp4`, codec h264_nvenc, yuv420p, AAC 192k, 30 fps. Use 60 fps only when source is 60+ fps.
- Always run `ffprobe` on the final to verify duration / resolution / codec before claiming the job is done.
