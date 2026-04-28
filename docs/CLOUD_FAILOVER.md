# Cloud Run failover for Mercury web UI

When the user's RTX 5090 is busy (TRIBE running, training, asleep) or they're
on mobile away from their tailnet, Mercury still needs to serve the `/cortex`
page and produce useful output. This doc maps the local-first / cloud-failover
architecture.

## Two surfaces, one URL

```
                                  brain.redteamkitchen.com
                                            │
                                            ▼
                            Cloudflare DNS — split routing
                            ├─ on-tailnet?     ──► Tailscale → 5090 desktop
                            └─ off-tailnet?    ──► Cloud Run (us-central1)
```

The DNS layer routes by network: anyone on the soumitlahiri tailnet hits the
GPU directly; anyone else (mobile, the public, Pixel Fold roaming away from
home Wi-Fi) gets the Cloud Run instance.

## What runs where

| Capability | On the 5090 (local) | On Cloud Run (failover) |
|---|---|---|
| Static SPA (mercury-web) | Vite dev server (`:5173`) | `serve` from the built `dist/` |
| LLM narration | Ollama gemma4:26b (free, local) | Vertex AI **Gemini 1.5 Flash** (~$0.05 per /cortex page load) |
| Real BOLD trace | Cortex backend (`:8766`) calls TRIBE v2 on the 5090 | Proxied via Cloudflare Tunnel back to the 5090 — Cloud Run waits |
| Brain renderer | Three.js client-side, no server work | Same client-side renderer, no server work |
| Cost | $0 | < $5/mo at expected traffic, well under Cloud Run free tier |

## Build and deploy

The Mercury web UI ships with a minimal Dockerfile + Cloud Run spec under
`mercury-web/`. One-shot deploy:

```bash
cd mercury-web
gcloud run deploy mercury-web \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --set-secrets GOOGLE_API_KEY=gemini-api-key:latest \
  --set-env-vars MERCURY_GPU_API=https://brain.redteamkitchen.com
```

Or via the spec file (recommended for auditability):

```bash
gcloud builds submit --tag gcr.io/rtk-prod-2026/mercury-web:latest
gcloud run services replace cloudrun.yaml --region us-central1
```

## How the page knows where it's running

`vite.config.ts` reads `VITE_DEPLOY_TARGET`:

| Build flag | What it does |
|---|---|
| `local` (default) | All inference local — Ollama for narration, Cortex backend for TRIBE |
| `cloudrun` | Narration falls back to Vertex AI Gemini; TRIBE requests proxy to `MERCURY_GPU_API` |
| `pixelfold` | Same as `cloudrun` but on-device Gemma 4 E4B is the *first* narration choice (MediaPipe LLM Inference); cloud is only used if the device runs hot |

## Pre-generated narration

The `mercury-web/src/data/cortex-narrations.json` file ships with the
pre-generated paragraphs from local `gemma4:26b`. **This means the Cloud Run
build has narration already baked in** — Vertex AI is only called on demand
when the user wants something not in the bundled set (e.g. narration of a
*specific* user-uploaded clip).

Regenerate the bundled narration any time the wording or scope changes:

```bash
cd mercury-web
node scripts/generate_cortex_text.mjs
```

(Ollama must be running locally; takes ~20s.)

## Mobile (Pixel 9 Pro Fold)

The Pixel Fold is special: it has a Tensor G4 NPU and 16 GB RAM, enough to
run **Gemma 4 E4B Q4_K_XL on-device** via MediaPipe LLM Inference. Configure
in `~/.mercury/config.yaml` on the phone (under Termux):

```yaml
narration_chain:
  - on_device:    gemma-4-e4b      # first choice — zero network
  - cloud:        vertex-ai-gemini # second — when on-device runs hot
  - skip_if_offline: true          # third — fall back to bundled JSON only
```

This makes the brain demo work on a plane.

## Cost ceiling

The free tier handles 2M requests/mo and 360,000 vCPU-seconds/mo. At the
expected traffic for a hackathon submission demo (a few hundred views over
the first week, a few thousand if the demo goes well on social), we stay
inside the free tier comfortably. **Worst case observed:** ~$2-3/month even
if the demo gets shared widely, dominated by Vertex AI Gemini calls when the
user actually requests a custom narration.

## Sanity checklist before flipping the DNS

- [ ] `dist/` builds clean — `npm run build` passes locally
- [ ] `node scripts/generate_cortex_text.mjs` re-ran recently — bundled JSON is up to date
- [ ] `gemini-api-key` secret exists in Secret Manager
- [ ] Cloudflare Tunnel pointing `brain.redteamkitchen.com` to the 5090 is up
- [ ] `tailscale serve` on the 5090 has the same path mounted at `/cortex` for tailnet hits
- [ ] First Cloud Run cold start < 3s (test with `curl -w '%{time_total}\n'`)
- [ ] `/cortex` page renders without the local Ollama running (uses bundled narration)
