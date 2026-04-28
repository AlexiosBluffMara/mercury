---
name: brain-viz
description: Turn any short video, audio clip, or text stimulus into an interactive 3D cortical activation visualization with three-tier narration. Use when the user asks to "see what their brain looks like watching X", wants a brain-response visualization of a clip, requests an fMRI-style overlay, or wants a creative neuroscience demo. Composes the cortex-bridge skill (TRIBE v2 pipeline) with three-js-component (R3F viewer) and gives the user a single browser-openable URL.
version: 0.1.0
author: Mercury
license: MIT
metadata:
  hermes:
    tags: [brain, fMRI, BOLD, three.js, R3F, neuroscience, creative, visualization]
    category: creative
    related_skills: [cortex-bridge, three-js-component, three-js-debug, glsl-shader]
  hackathon:
    target: nous-research-creative-2026
    track: creative
prerequisites:
  python_packages: [cortex]
  files: [D:/cortex]
  services:
    - "Cortex backend reachable on its FastAPI port (default 8765)"
    - "Three.js front-end built — D:/cortex/webapp or D:/mercury/mercury-web"
---

# Brain Viz — Video → 3D Cortex with Narration

Mercury's flagship creative skill: a video, audio clip, or short text in →
a 3D cortical activation map + three-tier narration out, all as one URL the
user can paste into a browser.

This skill is a *composer* — it doesn't do TRIBE v2 inference itself or
generate Three.js code from scratch. It chains the lower-level skills the
user already has installed.

## When to Use

- **"Show me what my brain looks like watching this video."**
- **"Visualize the BOLD response to this audio clip."**
- **"Make a creative brain demo for hackathon recording."**
- **"What would a research neuroscientist say about this stimulus?"**
- **"Toddler / clinician / researcher tier explanation of this clip's effect."**

**Do NOT use for:**
- Medical advice, diagnosis, or claims about specific people's brains.
  TRIBE v2 outputs are population-level group averages from training fMRI —
  always frame results that way.
- Long inputs. Hard cap is 50 seconds (`duration_trs=100` at 2 Hz). Trim
  inputs first; don't try to override `duration_trs` (silent corruption).
- Stimuli requiring informed-consent disclosure (gore, etc.) — Cortex's
  `media_gate` will reject; surface the rejection to the user, don't retry.

## How It Works End-to-End

```
       user provides video / audio / text (≤50 s)
                       │
                       ▼
   ┌─────────────────────────────────────────────────┐
   │  1. cortex-bridge.media_gate                    │
   │     Gemma 4 E4B vision-checks the input,        │
   │     classifies content, returns a safety verdict│
   └────────────────┬────────────────────────────────┘
                    │ accepted
                    ▼
   ┌─────────────────────────────────────────────────┐
   │  2. cortex-bridge.brain_scan                    │
   │     GPU swap: Gemma → TRIBE v2.                 │
   │     Returns 20,484-vertex BOLD trace × 100 TRs. │
   │     ~4–7 minutes on the 5090.                   │
   └────────────────┬────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────┐
   │  3. cortex-bridge.narrate (×3)                  │
   │     Gemma 4 26B — generates toddler / clinician │
   │     / researcher tier explanations of the trace.│
   └────────────────┬────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────┐
   │  4. three-js-component (existing scene reuse)   │
   │     The Cortex web-app already has a brain mesh │
   │     viewer.  POST the BOLD trace to its         │
   │     /api/scan/<id> endpoint — the viewer        │
   │     animates the activation in real time.       │
   └────────────────┬────────────────────────────────┘
                    │
                    ▼
       returns: { url, scan_id, tiers: {...} }
```

## Step-by-Step

### Step 1 — Verify cortex backend is reachable

Mercury's `cortex-bridge` exposes a state check:

```python
from mercury import cortex_bridge
state = cortex_bridge.cortex_state()
```

- `idle` or `gemma_active` → safe to start a scan
- `tribe_active` → another scan is in flight; tell the user "queued"
- `swapping` → wait briefly, re-poll
- `unavailable` → Cortex isn't installed/running. Tell the user to start it
  (`cd D:/cortex && uvicorn cortex.api.server:app --port 8765`) before this
  skill can be used.

### Step 2 — Run the scan

```python
result = cortex_bridge.brain_scan(
    media_path = "<absolute path or URL>",
    return_format = "bold_trace",   # 20484 × 100 float array
)
# result = {"scan_id": "...", "bold": [...], "duration_s": 50.0, "metadata": {...}}
```

If `media_gate` rejects the input, `brain_scan` raises `CortexError` with a
human-readable reason — surface that, don't retry.

### Step 3 — Generate three-tier narration

```python
tiers = cortex_bridge.narrate(
    scan_id = result["scan_id"],
    tiers   = ["toddler", "clinician", "researcher"],
)
# tiers = {"toddler": "...", "clinician": "...", "researcher": "..."}
```

Tier definitions:
- **toddler:** under 50 words, second-person, concrete metaphors, no jargon
- **clinician:** 100–200 words, clinical register, references brain regions
  by anatomical name (e.g. "primary visual cortex (V1)"), notes any
  unusual activation patterns
- **researcher:** 200–400 words, references TRIBE v2 paper terminology,
  cites approximate Glasser parcels, includes BOLD signal confidence

### Step 4 — Hand the user a URL

The Cortex web-app at `http://localhost:5173/scan/<scan_id>` (or the public
Cloudflare-Tunnel URL `https://brain.redteamkitchen.com/scan/<scan_id>`)
auto-loads the BOLD trace and renders it on a Glasser-parcellated cortex
mesh.

The page exposes:
- **Play/pause/scrub** through the 50-second BOLD timeline
- **Tier tabs** for the three narrations
- **Region inspector** — click any cortical region to see its activation
  curve and the most relevant narration excerpt

Return a single text answer to the user with the URL plus a one-sentence
preview of the toddler-tier narration so they immediately know whether
the scan worked.

## Output Contract

```python
{
  "url":      str,            # browser-openable
  "scan_id":  str,
  "duration": float,          # seconds
  "tiers":    {"toddler": str, "clinician": str, "researcher": str},
  "preview":  str,            # 1-sentence "lead" — same as tiers["toddler"][:120]
  "error":    Optional[str],  # only present on failure
}
```

## Error Modes (and how to surface them)

| Error | What happened | What to tell the user |
|---|---|---|
| `cortex_unavailable` | Backend not running | "Start Cortex first: `cd D:/cortex && uvicorn ...`" |
| `media_gate_rejected` | Gemma 4 flagged the input | Quote the reason verbatim — don't retry |
| `tribe_oom` | GPU couldn't allocate | "Free 22 GB of VRAM and retry — close other models" |
| `duration_overflow` | Input > 50 s | "Trim to ≤50 s and retry" |
| `network_error` | API call to backend failed | "Check Cortex is reachable on `:8765`" |

## Examples

**User:** *"Show me what my brain does watching this clip"* + attaches `cat.mp4`

**Agent flow:**
1. `cortex_state()` → `idle`
2. `brain_scan(media_path="cat.mp4", return_format="bold_trace")` → `scan_id=abc123`
3. `narrate(scan_id="abc123", tiers=[...])` → three strings
4. Reply:

> Done — your brain lights up most strongly in V1 and the
> superior temporal sulcus when watching this. Open it here:
> `https://brain.redteamkitchen.com/scan/abc123`
> Toddler version: "Your eyes-and-ears parts get really busy because
> there's a fluffy cat moving and meowing!"

## Hackathon Submission Notes (Nous Creative 2026)

This skill is the centerpiece of the Mercury submission to the **Nous
Research Hermes Agent Creative Hackathon** (deadline May 3, 2026).

For the demo recording:
1. Pre-warm Gemma 4 E4B and the Cortex backend (see `D:/TRIBEV2/DEMO_SCRIPT.md`)
2. Use a 20-second cat / animal-perception clip for visceral first-time
   wow factor
3. Show the three tier narrations side-by-side
4. Briefly switch the planner to `nousresearch/hermes-4-405b` to demonstrate
   multi-model orchestration (`/model nous-portal:nousresearch/hermes-4-405b`)
5. Briefly switch to `moonshotai/kimi-k2.6` to demonstrate Kimi Track
   eligibility (`/model nous-portal:moonshotai/kimi-k2.6`)

Trademark line required by both Nous + Google: "Gemma is a trademark of
Google LLC."
