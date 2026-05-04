---
name: cortex-bridge
description: Use Mercury's Cortex bridge to analyze video / audio / text stimuli through TRIBE v2 brain-foundation model. Use when the user provides a video, asks "what does the brain do when I watch X", asks for a brain scan, or requests a multi-tier neuroscience explanation of cortical activation.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  mercury:
    tags: [cortex, TRIBE, fMRI, BOLD, neuroscience, brain-scan, narration]
    category: research
    related_skills: [three-js-component, glsl-shader]
prerequisites:
  python_packages: [cortex]
  files: [D:/cortex]
---

# Cortex Bridge — Brain Response Analysis

Mercury can drive Cortex's TRIBE v2 pipeline through `mercury/cortex_bridge.py`.
Cortex must be installed in the Mercury venv (`pip install -e D:/cortex`) and
its scheduler must be reachable.  The bridge degrades gracefully when Cortex
is missing — `cortex_state()` returns `"unavailable"` and the four cortex
tools won't show up in the toolset.

## When to Use

- User uploads or references a video / audio file and asks "what would
  the brain do" / "predict the cortical response" / "run a brain scan".
- User asks for a multi-tier explanation of an existing scan result
  (toddler, clinician, researcher levels).
- User wants a 3D visualization of cortical activations.

**Do NOT use** for medical advice, individual diagnosis, or claims about
specific people's brains.  TRIBE v2 outputs are population-level group
averages from training fMRI — frame results that way.

## 1. Check the GPU is free first

Cortex's scheduler enforces a hard lock — TRIBE v2 (~22 GB) and Gemma 4
E4B (~10 GB) cannot coexist in the 5090's 32 GB.  Before starting:

```python
from mercury import cortex_bridge
state = cortex_bridge.cortex_state()
# one of: "idle", "gemma_active", "tribe_active", "swapping", "unavailable"
```

- `idle` or `gemma_active` → safe to call `brain_scan` (it'll swap).
- `tribe_active` → another scan is in flight; queue or wait.
- `swapping` → wait briefly and re-check.
- `unavailable` → Cortex isn't installed.  Tell the user, don't fake it.

## 2. The four tools (registered as toolset "cortex")

| Tool | Purpose | Latency |
|---|---|---|
| `describe_input` | Gemma 4 vision pre-classifies media type and content | ~2-5s |
| `brain_scan` | Full TRIBE v2 inference end-to-end (preprocess → infer → narrate) | 4-7 min |
| `narrate` | Generate tier 0-6 narration of an existing scan result (no GPU swap) | ~10-30s |
| `visualize` | Heatmaps, bar charts, 3D viewer URLs from scan results | ~2-5s |

Standard happy-path order: `describe_input` → `brain_scan` (with
`include_narration=true`) → `visualize` if the user wants charts.

## 3. Tier system for narration

| Tier | Audience | Use when |
|---|---|---|
| 0 | Toddler (3-5y) | User explicitly asks "explain like I'm 5" |
| 1 | Grandparent | Family-friendly, no neuroscience jargon |
| 2 | Curious adult (default) | Most general use |
| 3 | High-school student | Some scientific vocabulary |
| 4 | College-educated | Anatomical region names OK |
| 5 | Clinician | Neurologist / psychiatrist level |
| 6 | Researcher | Full ROI / network / metric language |

When the user doesn't specify, default to tier 2.  When they're a
researcher (Cortex is built for them) and the request is technical,
tier 5 or 6.

## 4. Honesty about latency

Brain scans take 4-7 minutes on the 5090.  Tell the user the wait is
expected before starting.  Mercury's `terminal` tool can run the scan
in the background with `notify_on_complete=true` so the user can do
other work and get notified.  Don't promise sub-minute scans.

## 5. Result shape (from `brain_scan`)

```python
{
  "ok": True,
  "top_rois": ["VisualA_L_5", "MotorB_R_2", ...],   # Schaefer-400 region names
  "peak_frame": 38,
  "peak_time_s": 19.0,
  "num_timepoints": 100,                            # always 100 (50s @ 2Hz)
  "num_vertices": 20484,                            # always 20484
  "duration_s": 50.0,
  "processing_time_s": 287.4,
  "media_info": { ... },
  "vision_analysis": { "analyses": [...] },
  "narration": "...",                               # if include_narration
  "narration_tier": 2,
}
```

`top_rois` are Schaefer-400 region labels — chunk-friendly to feed into
the `narrate` tool or a Three.js scene that lights up specific cortical
parcels.

## 6. Failure modes

| `error` | Meaning | Recovery |
|---|---|---|
| `file_not_found` | Path doesn't exist | Re-check the upload, ask the user to reattach |
| `unsupported_format` | Not in the .mp4/.wav/.txt allowlist | Convert with ffmpeg first |
| `too_long` | >300s media | Trim with ffmpeg; only the last 50s reach TRIBE anyway |
| `oom` | GPU OOM during inference | Restart Ollama, retry once; if persistent suggest a shorter clip |
| `preprocessing_failed` | ffmpeg / probe failed | Surface the inner message; usually a corrupt upload |
| `cortex_unavailable` | Cortex not in venv | `pip install -e D:/cortex` then restart Mercury |

## 7. Verification before reporting "done"

1. The scan response has `ok: true` and `processing_time_s` is reasonable
   (200-450s for a 50s clip).
2. `top_rois` is a non-empty list of strings.
3. If narration was requested, it's a coherent paragraph (not
   `"(Narration unavailable: ...)"`).
4. If the user asked for a visualisation, the output includes a chart
   path or a 3D viewer URL.

## Pitfalls

1. **Never override `duration_trs`.** TRIBE v2 is hard-locked at 100
   TRs; touching that knob silently corrupts inference.  Cortex's
   pipeline enforces it — never advise the user to patch around it.
2. Don't mix Gemma and TRIBE inference in the same turn — even though
   the scheduler swaps for you, the swap costs 15-20s on the way in
   and 5-8s on the way back; minimise round-trips.
3. **Population-level disclaimer.**  TRIBE outputs reflect training
   subjects' aggregated responses, not the user's brain.  Always
   include a one-line disclaimer in user-facing narration.
4. The bridge raises `CortexError` envelopes from the Cortex side.
   Pass them through verbatim rather than rewrapping — they have
   structured fields the WebUI uses.
5. Do NOT diagnose medical conditions or make claims about individuals
   from a scan result.  If asked, decline and route to a clinician.
