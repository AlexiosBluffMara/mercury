# ComfyUI workflows

Drop ComfyUI graph JSONs (saved via *Save (API Format)*) here. Mercury's
`comfyui` skill loads them by filename — no code changes needed to add
a new workflow.

## Naming convention

- `_default_*.json` — used as the tier-1 default for a model family
- `_components/*.json` — sub-graphs that the tier-3 composer can stitch
- `<descriptive-name>.json` — tier-2 saved workflows for specific outputs

## Examples (TODO — populate during post-hackathon polish)

- `_default_sdxl.json` — single-prompt SDXL @1024²
- `_default_flux.json` — single-prompt Flux dev fp8
- `brain-cinema-poster.json` — illustration for a Cortex narration
- `abm-isu-collab-banner.json` — UNIQLO-style horizontal banner asset
- `etsy-listing-square.json` — 1024×1024 product listing for philanthropytraders.com

When you save a new workflow:

```
# In ComfyUI web UI:
Settings → "Enable Dev mode Options"
Then in the toolbar: "Save (API Format)" → save here.
```

Mercury reads the workflow at runtime via `prompt_overrides` to inject
the user's prompt / seed / model into the right node IDs.
