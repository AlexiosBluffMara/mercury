---
name: comfyui
description: Drive a local ComfyUI instance for image and video generation workflows. Use when the user asks to generate an image with Stable Diffusion / Flux / SDXL / WAN / Hunyuan / any node-based diffusion pipeline, wants to run a saved ComfyUI workflow JSON, needs to assemble a pipeline of nodes (KSampler, VAE Decode, ControlNet, IPAdapter, AnimateDiff), or wants Mercury to compose images that get folded into a brain-viz / pitch-deck / Cortex narration. Targets a local ComfyUI server (default http://localhost:8188) — never sends prompts to a hosted SaaS.
version: 0.1.0
author: Mercury
license: MIT
metadata:
  mercury:
    tags: [comfyui, image-generation, diffusion, sdxl, flux, wan, hunyuan, video-generation, workflows, creative]
    category: creative
    related_skills: [brain-viz, ascii-video, baoyu-infographic, creative-ideation]
  hackathon:
    target: nous-research-creative-2026
    track: creative
prerequisites:
  python_packages: [requests, websocket-client, pillow]
  services:
    - "ComfyUI server reachable at $COMFYUI_URL (default http://localhost:8188)"
  notes:
    - "Run ComfyUI locally: clone github.com/comfyanonymous/ComfyUI, `pip install -r requirements.txt`, `python main.py --listen`."
    - "On the RTX 5090 baseline, SDXL 1024×1024 takes ~3 s; Flux dev fp8 takes ~12 s; HunyuanVideo 5 s clip takes ~2 min."
    - "Workflow JSONs live in skills/creative/comfyui/workflows/ — drop new ones in to make them callable."
---

# ComfyUI — local diffusion pipelines

Mercury's image and short-video generation surface. Wraps a **local
ComfyUI** server (no SaaS dependency, no per-image fee) and exposes it
as a skill so the agent can mix generated imagery into other workflows
— a Cortex narration that needs an illustrative still, a brain-viz
poster, a pitch deck thumbnail, an Etsy listing image for the
philanthropytraders.com store.

ComfyUI is **the** node-based diffusion runner. Everything else in
this skill set (brain-viz, ascii-video, baoyu-infographic) can call
this one to assemble images on demand.

## When the dispatcher should auto-load this skill

The skill loads automatically when the user message references any of:

- "generate an image of …", "draw …", "render …", "make a picture of …"
- A specific diffusion model: SDXL, Flux, Pony, SD 1.5, Hunyuan, WAN, AnimateDiff
- A node concept: KSampler, VAE Decode, ControlNet, IPAdapter, LoRA, ip2p
- A workflow file: "run this workflow.json", "queue prompt for …"
- An adjacent creative ask that needs imagery: "make a pitch deck for X", "draft an Etsy listing for …"

Don't auto-load on generic "make me a logo" — that goes through `creative-ideation` first to decide the medium.

## What the skill does

### Tier 1 — single-prompt generation

```
/comfyui prompt="a cardinal red brain rendered in fsaverage5 mesh, ISU palette" model=sdxl size=1024
```

Mercury POSTs a prompt-only workflow to `${COMFYUI_URL}/prompt`, polls
the WebSocket for completion, downloads the resulting PNG, and surfaces
the path back. Default model = SDXL. Default workflow =
`workflows/_default_sdxl.json`.

### Tier 2 — saved workflow execution

```
/comfyui workflow=brain-cinema-poster.json prompt_overrides={"positive":"…","seed":42}
```

The user (or another skill) hands Mercury a known workflow JSON. Mercury
patches the `prompt_overrides` into the right node IDs, queues it, waits
for completion. Used when the workflow has carefully-tuned ControlNet
or IPAdapter nodes that shouldn't be regenerated.

### Tier 3 — workflow composition

```
/comfyui compose nodes=["sdxl","upscale-2x","face-restore"] prompt="…"
```

Mercury composes a workflow JSON by stitching together node templates
from `workflows/_components/`. This is the closest to "talking to the
graph" — the agent reasons about which nodes to chain. Slower; only
worth it for new compositions.

### Tier 4 — short video

```
/comfyui video model=wan-2.1 prompt="brain scan rotating, ISU red activation pulse" frames=120
```

Calls a video workflow (HunyuanVideo, WAN 2.1, AnimateDiff, etc).
Returns an MP4 path. Real-time monitoring of progress is provided via
the `comfyui_progress` event on Mercury's broadcast bus so the WebUI
or terminal can show a progress bar.

## Hardware tiers

ComfyUI scales with VRAM:

| GPU | What this skill can run |
|---|---|
| RTX 5090 (32 GB, baseline) | SDXL @1024², Flux dev fp8, SD3.5 medium, HunyuanVideo 5 s @540p |
| RTX 6000 Ada / L40S (48 GB) | Flux dev bf16, Flux schnell full quality, HunyuanVideo 10 s @720p |
| A100 (40 GB) / A100 (80 GB) | Concurrent multi-batch; Flux training; long-form video |
| H100 (80 GB) | Production rate; multiple workflows in parallel |

This is the same scale-up curve as Cortex itself — see the Cortex docs
for the full target table.

## Configuration

```yaml
# ~/.mercury/config.yaml
skills:
  comfyui:
    url: http://localhost:8188             # override with COMFYUI_URL env var
    default_model: sdxl                    # sdxl | flux-dev | flux-schnell | sd3.5
    default_size: 1024
    output_dir: ~/.mercury/output/comfyui  # where generated files land
    workflows_dir: skills/creative/comfyui/workflows
    timeout_seconds: 600                   # for long video runs
```

## Workflow library

Workflows live as JSON files under `workflows/`. Each is a complete
ComfyUI graph saved from the UI ("Save (API Format)"). Mercury's
dispatcher loads them by filename:

```
workflows/
  _default_sdxl.json           # tier 1 default
  _default_flux.json           # alternative tier 1
  _components/                 # node templates for tier 3 composition
    upscale-2x.json
    face-restore.json
    controlnet-depth.json
  brain-cinema-poster.json     # tier 2 — Cortex output illustration
  abm-isu-collab-banner.json   # tier 2 — UNIQLO-style brand banner
  etsy-listing-square.json     # tier 2 — philanthropytraders.com listings
```

To add a workflow: design it in the ComfyUI web UI, click *Save (API
Format)*, drop the JSON in `workflows/`, and reference by filename.

## Offline / air-gapped operation

ComfyUI itself runs entirely offline if model weights are pre-downloaded
to `models/checkpoints/`, `models/loras/`, etc. Mercury's `comfyui`
skill doesn't introduce any new outbound calls — it talks only to
`localhost:8188`. Suitable for ACCESS HPC and other air-gapped
academic environments.

## Composition with other Mercury skills

- **`brain-viz`** can call this skill to generate illustrative stills
  for the narration panels (e.g. "show what the V1 region typically
  responds to").
- **`baoyu-infographic`** uses this for hero images in long-form
  infographic generation.
- **`creative-ideation`** suggests prompts; this skill executes them.
- **`cortex-bridge`** can attach a generated image as the thumbnail
  for an uploaded scan.

## Limitations

- This is a **scaffold**. The first version ships only Tier 1 (single
  prompt → SDXL/Flux). Tier 2/3/4 require workflow JSONs and integration
  testing with the live ComfyUI server.
- No cloud failover. ComfyUI is deliberately local-only — see the
  Mercury thesis: privacy-as-architecture, not privacy-as-promise.
- Image safety filtering is the operator's responsibility. ComfyUI has
  no built-in NSFW gate; Mercury doesn't add one. Configure the
  ComfyUI server's safety settings before exposing this to other users.

## Authorship

Scaffolded by Mercury for the Nous Research × Kimi Creative Hackathon
2026 submission. Production workflows will be generated and tuned
during the post-hackathon polish phase, alongside the
philanthropytraders.com Etsy store imagery and the Cortex demo
illustrations.
