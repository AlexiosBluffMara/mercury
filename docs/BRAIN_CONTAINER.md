# Mercury Brain — Gemma 4 inference container

A single Cloud Run service that serves Gemma 4 inference behind an
OpenAI-compatible HTTP surface. Mercury (`agent/brain_client.py`) and
Cortex both call into this. ABM × Illinois State University research.

## Why Ollama, not vLLM

- **Multimodal Gemma 4** (vision + audio) is supported in Ollama today;
  vLLM has not landed it yet. Mercury's reasoning/skill flows assume the
  multimodal SKU is reachable behind the same surface as the text-only
  one, so we standardize on the runtime that supports the largest set.
- Ollama already speaks an OpenAI-compatible subset
  (`/v1/chat/completions`); we only need a thin facade to fix the
  rough edges (SSE delta format, `/v1/models`, `/healthz`, `/ready`).
- The user runs Ollama locally on the 5090. Same runtime everywhere
  reduces drift between dev and prod.
- Cloud Run for GPUs accepts the upstream `ollama/ollama:latest` image
  with no patching.

## Topology

```
client ──HTTP──► FastAPI facade :8080  ──HTTP──► ollama daemon :11434
                  (OpenAI surface,                (native /api/chat,
                  /healthz, /ready)                 /api/generate)
```

Public port is **8080** (the facade). Ollama stays on `127.0.0.1:11434`
inside the container so the OpenAI translation is the only public surface.

## Endpoints

| Path                       | Purpose                                       |
|----------------------------|-----------------------------------------------|
| `POST /v1/chat/completions`| OpenAI chat (streaming + non-streaming)       |
| `POST /v1/completions`     | OpenAI text completion                        |
| `GET  /v1/models`          | Installed models in OpenAI list format        |
| `GET  /healthz`            | Liveness — facade responds                    |
| `GET  /ready`              | Readiness — Ollama up and at least one model  |
| `*    /api/*`              | Pass-through to Ollama native API             |

Streaming responses use OpenAI's SSE delta format:

```
data: {"id":"chatcmpl-...","choices":[{"delta":{"content":"Hello"}}]}
data: [DONE]
```

## Calling from Mercury or Cortex

```python
# agent/brain_client.py (built in parallel)
reply = await brain_client.chat(messages, model="gemma4:e4b")
```

The client points at whichever Cloud Run URL the deploy workflow prints:

```
mercury-brain-cold:  https://mercury-brain-cold-XXXXXX-uc.a.run.app
mercury-brain-warm:  https://mercury-brain-warm-XXXXXX-uc.a.run.app
```

Both require an OIDC token. Mercury and Cortex use their own runtime
SAs with `roles/run.invoker` on these services.

## SKUs

| Build arg                  | Image tag                  | Use                          |
|----------------------------|----------------------------|------------------------------|
| `BRAIN_MODEL=gemma4:e4b`   | `mercury-brain:e4b-<tag>`  | Default. Text. ~5 GB.        |
| `BRAIN_MODEL=gemma4:26b-moe` | `mercury-brain:26bmoe-<tag>` | Multimodal (vision/audio). ~16 GB. |
| (future) `gemma4:31b-r`    | `mercury-brain:31br-<tag>` | Reasoning SKU. Separate svc. |

The 26B-MoE and 31B reasoning images deploy as **additional** Cloud Run
services (not as a replacement for the E4B service); the E4B service
remains the warm-pool target because of its lower per-instance cost.

## Cloud Run config

Both services request:

```
--gpu=1 --gpu-type=nvidia-l4 --memory=16Gi --cpu=4 --no-cpu-throttling
--port=8080 --no-allow-unauthenticated --ingress=internal
```

| Service              | min | max | CPU allocation | Concurrency | Use case                  |
|----------------------|-----|-----|----------------|-------------|---------------------------|
| `mercury-brain-cold` | 0   | 10  | request-only   | 4           | Batch / non-interactive   |
| `mercury-brain-warm` | 1   | 3   | always         | 4           | Discord interactive flows |

## Cold-start curve

| State                                    | Time to first token |
|------------------------------------------|---------------------|
| Empty container (image not yet on node)  | ~30 s               |
| Image pulled, model not in VRAM          | ~10–12 s            |
| Model already loaded (warm pool steady)  | ~1.5–2 s            |

The model is **pre-pulled into the image** at build time (the
`RUN ollama pull` step), so we never pay the 5 GB Hugging Face download
on cold-start — only the read from container layer to the GPU node and
the load into VRAM. The `start.sh` warms the model into VRAM with a
no-op generate before exposing the facade, so `/ready` only goes 200
once VRAM is hot.

## Cost analysis

Cloud Run for GPUs (us-central1, May 2026 published rates):

| Resource        | Rate        |
|-----------------|-------------|
| L4 GPU          | ~$0.70/hr   |
| 4 vCPU          | ~$0.097/hr  |
| 16 GiB memory   | ~$0.0107/hr |
| **Total / hr**  | **~$0.81**  |
| **Total / min** | **~$0.0135**|

### Warm pool 24/7
1 instance × $0.81/hr × 730 hr/mo ≈ **$591/month** floor. Adding
billed-out CPU (`--no-cpu-throttling`) we round to **~$540–600/month**
depending on the share of idle vs serving time.

### Warm pool with the 07:00–23:00 schedule
16 hours × 30 days = 480 hr/month × $0.81/hr ≈ **$389/month**. After the
ramp-down (Cloud Run keeps the instance for ~5 min after the last
request before scaling to zero) plus the cold-pool bursts overnight,
realistic monthly is **~$340–400/month**.

### Per-token cost
At the warm pool, per-token cost is governed by **floor utilization**:
when traffic is high the floor amortizes near-zero per token; when
traffic is sparse the floor is the entire bill.

For the cold pool (scales to zero), cost is purely usage-based:
1 minute of GPU = ~$0.0135 ≈ ~600 tokens at E4B's ~10 tok/s on L4 →
**~$0.022 / 1 K tokens**.

## Roll-out plan

1. **Phase 1 — cold-only.** Tag `brain-v0.1.0`, let GH Actions build
   the E4B image and create both services, but set
   `mercury-brain-warm` `min-instances=0` for a week. Cortex and
   Mercury both call the cold service. Watch P99 first-token latency.

2. **Phase 2 — warm pool, scheduler off.** Bump warm `min-instances=1`
   manually. Validate that interactive Discord flows are <2 s
   first-token. Scheduler still off — pay the 24/7 floor while we
   confirm reliability.

3. **Phase 3 — scheduler on.** Apply
   `gcp/scheduled-warm-ping.yaml` to cap the warm window at
   07:00–23:00 Chicago. Per-month bill drops from ~$590 to ~$340.

## Deploy

```
git tag brain-v0.1.0
git push origin brain-v0.1.0
```

The `deploy-brain.yml` workflow:

1. Builds `mercury-brain:e4b-v0.1.0` and `:e4b-latest`
2. Builds `mercury-brain:26bmoe-v0.1.0` and `:26bmoe-latest`
3. Pushes both to `us-central1-docker.pkg.dev/abm-isu/cortex/`
4. Applies `gcp/cloud-run-brain.yaml` with the new image tag
5. Removes any `allUsers` invoker bindings (defense-in-depth)
6. Smokes `/ready` on the warm service

First deploy must have already provisioned:

- The Artifact Registry repo `cortex` in `us-central1`
- The service account `brain-runtime@abm-isu.iam.gserviceaccount.com`
- The WIF provider used by the existing `gcp/setup-wif.sh` flow
- An IAM binding letting Mercury/Cortex SAs `roles/run.invoker` on the
  two brain services

## Configuration

| Env var                | Default       | Notes                            |
|------------------------|---------------|----------------------------------|
| `BRAIN_MODEL`          | `gemma4:e4b`  | Ollama model tag to serve        |
| `PORT`                 | `8080`        | Facade port                      |
| `OLLAMA_URL`           | (auto)        | Override only for testing        |
| `OLLAMA_KEEP_ALIVE`    | `24h`         | Keep model in VRAM               |
| `BRAIN_REQUEST_TIMEOUT`| `300`         | seconds; matches Cloud Run cap   |

The warm-ping schedule (07:00–23:00 Chicago) lives in
`gcp/scheduled-warm-ping.yaml` under `config:`. Re-render the cron
with different `wake_hour_start` / `wake_hour_end` /
`default_time_zone` for other deployments.
