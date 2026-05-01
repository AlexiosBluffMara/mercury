# Mercury — Cloud Architecture

**`ALEXIOS BLUFF MARA × ILLINOIS STATE UNIVERSITY`**
*Research conducted in association with [Illinois State University](https://illinoisstate.edu), Bloomington–Normal, IL.*

---

```yaml
# TLDR
what:    Mercury as a multi-tenant SaaS on Google Cloud — Discord-first, scale-to-zero,
         per-user isolated context, public fMRI upload + TRIBE v2 retraining loop.
not:     A managed-API wrapper. Hot path is open-weight Gemma 4 on Cloud Run GPUs
         (or the Chicago 5090 via Cloudflare Tunnel) — no third-party LLM in the loop.
cost:    ~$0.0008 / 1k output tokens (E4B) → ~$0.18 / user / month at the 1k-user tier.
sla:     interactive < 2s first token (warm pool), balanced < 8s, batch < 60s.
status:  Planning. Local 5090 + Snowy The Bot + cortex.redteamkitchen.com are live;
         Cloud Run brain container, fMRI portal, and Vertex AI training are unbuilt.
```

---

## 1. Vision

Mercury today is a six-door personal agent running on a single RTX 5090 in Chicago, fronted by Snowy The Bot in the **Alexios Bluff Mara** Discord. It is the orchestration layer for [Cortex](https://github.com/AlexiosBluffMara/cortex) — the brain-response analysis stack we built for the Gemma 4 Good Hackathon and the Nous × Kimi Creative Hackathon. The 5090 path is fast and free at the margin. It is also a single point of failure, single-tenant, and incapable of letting strangers upload fMRI scans to extend TRIBE v2.

The next chapter of the project is multi-tenant. Cloud Mercury is the same agent — same persona, same skills, same memory schema — running as a Cloud Run service that anyone with a Discord account can talk to. The local 5090 stays in the loop as the *preferred* compute target when its `/api/utilization` endpoint says it is accepting work; otherwise traffic lands on Cloud Run with an L4 GPU. Everything scales to zero between requests. A single warm instance keeps the interactive tier hot for known operators.

Two things this enables that we cannot do today:

1. **Population-augmented TRIBE v2.** Anyone with a Discord account can run `/upload-fmri` and contribute an anonymized scan. When N opted-in scans accumulate, we trigger a Vertex AI custom training job to update TRIBE v2 against population data — moving the model away from its 25-subject Courtois NeuroMod baseline and toward something that generalizes.
2. **Mercury as an actual product.** Soumit Lahiri (Alexios Bluff Mara LLC, dba Red Team Kitchen) has a working stack on his desk. Cloud Mercury is the version that someone else can use without owning a 5090 — a research project framed as a plausible startup, with the ABM × Illinois State University collaboration as its institutional home.

This document is the master plan for the Mercury side. The Cortex-side companion is at `D:\cortex\docs\CLOUD_ARCHITECTURE.md`.

---

## 2. Topology

```
═══════════════════════════════════════════════════════════════════════════════
                       INTERNET (ANYONE WITH A DISCORD ACCOUNT)
═══════════════════════════════════════════════════════════════════════════════
        │                                          │
        │  /chat /think /upload-fmri /scan         │  https://mercury.redteamkitchen.com
        │  /memory /skills /status                 │  (Discord OAuth, web fallback)
        ▼                                          ▼
 ┌─────────────────────────┐         ┌─────────────────────────────────────┐
 │  Discord Gateway         │         │  Cloudflare CDN + DDoS (free)       │
 │  Snowy The Bot           │◄───────►│  CNAME → Cloud Run service URL      │
 │  ABM server + invitees   │         └─────────────────────────────────────┘
 └────────────┬─────────────┘                       │
              │ websocket                           │
              ▼                                     ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  mercury-gateway        Cloud Run (CPU only, min=1, region=us-central1) │
 │  ─────────────────                                                      │
 │  • Verifies Discord signature / OAuth token                             │
 │  • Loads users/{discord_id}/profile from Firestore                      │
 │  • Picks latency tier: interactive | balanced | batch                   │
 │  • Routes to brain via internal HTTP (WIF-authed)                       │
 │  • Streams response back over Discord webhook / Cloudflare              │
 │  • Writes turn to users/{discord_id}/conversations/{thread_id}          │
 └────┬─────────────────────────────────────┬──────────────────────────────┘
      │                                     │
      │ (interactive / known operator)      │ (balanced + batch / anon)
      ▼                                     ▼
 ┌──────────────────────────┐     ┌────────────────────────────────────────┐
 │ gemma-brain-hot           │     │ gemma-brain-cold                        │
 │ Cloud Run + L4 GPU        │     │ Cloud Run + L4 GPU                      │
 │ min=1, max=4              │     │ min=0, max=20                           │
 │ CPU always allocated      │     │ Request-based billing                   │
 │ Gemma 4 E4B (vLLM, OAI)   │     │ Gemma 4 26B MoE / 31B (Ollama)          │
 │ ~2s first token           │     │ 8–60s first token incl. cold start      │
 └────┬──────────────────────┘     └────┬───────────────────────────────────┘
      │                                 │
      └──────────────┬──────────────────┘
                     │
                     │ (5090 reachable + accepting + tribe_active==False)
                     ▼
        ┌──────────────────────────────────────┐
        │ Cloudflare Tunnel rtk-5090           │
        │ → 192.168.0.34 (Chicago workstation) │
        │ → Ollama :11434 / Cortex :8765       │
        └──────────────────────────────────────┘
                     ▲
                     │  preferred path when local GPU is free
                     │
 ┌───────────────────┴─────────────────────────────────────────────────────┐
 │                    USER STATE (Firestore Native, us-central1)            │
 │                                                                          │
 │  users/{discord_id}/                                                     │
 │    ├── profile           (display name, locale, opt-ins, KMS key alias)  │
 │    ├── memory/           (cross-session facts, vector embeddings)        │
 │    ├── conversations/    (thread_id → ordered turns)                     │
 │    └── fmri_scans/       (scan_id → metadata, GCS pointer, consent)      │
 │                                                                          │
 │  Rules: deny-by-default; only request.auth.uid == discord_id can read.   │
 └─────────────────────────┬────────────────────────────────────────────────┘
                           │
                           ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │       fMRI STORAGE  (GCS: cortex-fmri-uploads, CMEK + per-user keys)    │
 │       ─────────────                                                      │
 │       gs://cortex-fmri-uploads/{discord_id}/{scan_id}/{file}            │
 │       NIfTI / DICOM / BIDS / .mat / EDF — signed-URL upload only        │
 │       Lifecycle: 30-day soft-delete grace; 1-year retention if opt-in   │
 └────────────┬────────────────────────────────────────────────────────────┘
              │ object.finalize → Pub/Sub (cortex-fmri-finalize)
              ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  cortex-fmri-validator   Cloud Function (gen2)                          │
 │  • NIfTI header / DICOM tag / BIDS structure check                      │
 │  • De-identification audit (no PHI in DICOM tags)                       │
 │  • Writes fmri_scans/{user_id}/{scan_id} record                         │
 │  • DMs the user on Discord with verdict                                 │
 └────────────┬────────────────────────────────────────────────────────────┘
              │  (when N=50 opted-in scans accumulate)
              ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  TRIBE v2 RETRAIN — try local first, cloud second                       │
 │                                                                          │
 │   ┌───────────────────────────┐      ┌────────────────────────────────┐│
 │   │ Local 5090 (preferred)    │      │ Vertex AI custom training      ││
 │   │ via Cloudflare Tunnel     │      │ a2-highgpu-8g (8× A100 40GB)   ││
 │   │ /api/utilization gates    │  OR  │ ~$33.07/hr managed             ││
 │   │ (need >24 GB free, no     │      │ spot tier ~$9.92/hr            ││
 │   │  active tribe job)        │      │ Cloud Run can't do this        ││
 │   └─────────────┬─────────────┘      └─────────────┬──────────────────┘│
 │                 └──────────────┬─────────────────────┘                  │
 │                                ▼                                        │
 │              gs://cortex-tribe-models/{train_run_id}/                   │
 │              (versioned weights — smoke-tested before promotion)        │
 └────────────┬────────────────────────────────────────────────────────────┘
              │  promoted weights deployed to:
              ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  CORTEX INFERENCE                                                        │
 │  ──────────────                                                          │
 │  • Local: 5090 reloads from gs:// on next idle window                   │
 │  • Cloud: cortex-tribe-worker Cloud Run (L4 GPU) pulls on next deploy   │
 │  • Discord users get a DM: "TRIBE v2 has been updated — your scans     │
 │    contributed to train_run_id=…"                                       │
 └─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-tenancy model

The Discord user ID (a 17-19 digit snowflake) is the primary key for everything in the system. There is no separate "Mercury account." If you can prove you are `discord_id=219475…`, you own that namespace.

**Firestore document layout (per tenant):**

```
users/{discord_id}/
  profile                 (single doc — display name, locale, opt-ins, kms_key_alias)
  memory/{fact_id}        (cross-session profile facts + vector embeddings)
  conversations/{thread_id}/turns/{turn_id}
  fmri_scans/{scan_id}    (format, dims, TR, voxel size, anonymization, opt_in_train)
  skills_state/{skill}    (per-skill cache, e.g. last chicago-tax-legal lookup)
```

**Access rules (deny-by-default):**

```
match /users/{uid}/{doc=**} {
  allow read, write: if request.auth.uid == uid;
}
match /fmri_scans_index/{scan_id} {                  // training-only projection
  allow read: if hasRole("training-job-worker");
  allow write: if false;                             // server-side only
}
```

The brain container never reads Firestore directly. The gateway loads the tenant's profile + recent memory, packs it into a request-scoped context object, and passes it to the brain over an internal Cloud Run URL authenticated with Workload Identity Federation. The brain is stateless — it sees only what the gateway hands it.

**Per-user encryption for sensitive data.** fMRI uploads are encrypted at rest with a per-user key managed in Cloud KMS (alias `users/{discord_id}/scan-key`). The KMS key is wrapped under the project-level CMEK. Revocation = destroy the per-user key, then GCS lifecycle re-encrypts (or evicts) the user's prefix on the next sweep. This makes "delete my scans" a one-call operation that cryptographically forecloses recovery, without paying the cost of synchronous large-file deletes.

**Rate limits.**
- Anonymous web (no Discord auth): 10 req/min, batch tier only, 31B model.
- Authenticated Discord OAuth: 60 req/min, all tiers, all models.
- Known operator (allowlisted Discord IDs): 600 req/min, warm pool.

---

## 4. Identity & auth

| Surface                      | Auth                                         | Backend                            |
|------------------------------|----------------------------------------------|------------------------------------|
| Discord bot DM / slash       | Discord Interaction signature (Ed25519)      | Gateway verifies, looks up `discord_id` |
| Web `mercury.redteamkitchen.com` | Discord OAuth2 → JWT cookie              | Gateway issues 24h JWT             |
| Internal: gateway → brain    | Workload Identity Federation, Cloud Run IAM  | `roles/run.invoker` on brain only  |
| Cloud Function → Firestore   | WIF + service account                        | Custom claim `role=training-worker`|
| Operator alerts              | Outbound Discord webhook                     | Stored in Secret Manager           |

The Discord OAuth handshake on the web surface is the same identity as the bot — that is the whole point. The OAuth `id` claim is the user's `discord_id`. The gateway therefore can hand a web request the same memory and the same Firestore namespace as a Discord DM, with no separate registration step. The user already proved who they are by authenticating to Discord; we trust that proof.

---

## 5. Cost analysis — Gemma brain selection

The four Gemma 4 SKUs we benchmark internally (numbers calibrated against the local 5090 plus Cloud Run + L4 estimates; cloud-cost basis is **~$0.67/hr GPU + ~$0.05/hr CPU/RAM** on Cloud Run for GPUs, Tier-1 region, no zonal redundancy):

| Model           | VRAM   | Throughput          | Best for                  | $/1k tokens out (est.) | Cold-start (s) |
|-----------------|--------|---------------------|---------------------------|------------------------|----------------|
| Gemma 4 E4B     | 10 GB  | 194 tok/s on 5090   | default chat, low latency | ~$0.0008               | ~4             |
| Gemma 4 26B MoE | 16 GB  | 132 tok/s on 5090   | reasoning + multimodal    | ~$0.0021               | ~8             |
| Gemma 4 27B     | 22 GB  | 51 tok/s on 5090    | quality fallback          | ~$0.0048               | ~11            |
| Gemma 4 31B     | 22+ GB | 42 tok/s on 5090    | top-tier, deep think      | ~$0.0058               | ~13            |

**Math behind $/1k tokens (E4B example):**

```
GPU + CPU: $0.67 + $0.05 = $0.72/hr  →  $0.0002 / sec
At 194 tok/s: 1k output tokens = 5.15 sec  →  $0.00103 GPU-time
Plus ~25% overhead for network + framework + tokenization →  ≈ $0.0008–$0.0013 / 1k tok
```

The E4B number is *cheaper than the GPU-hour math implies* because cloud E4B cannot match the 5090's 194 tok/s — call it ~80 tok/s on L4. We average warm + cold + 5090-tunneled paths weighted by traffic mix, and the 5090 path's marginal cost is essentially zero (electricity only, ~$0.006/hr at idle scaling to ~$0.40/hr under full GPU load on Chicago grid power). The blended figure lands at the table number.

**Warm-pool monthly cost** (single L4 instance, `min-instances=1`, CPU always allocated, 24/7):

```
$0.67 GPU/hr × 730 hr  =  $489.10 / month   ← dominant cost
$0.05 CPU+RAM/hr × 730 = $ 36.50 / month
Cron warm-ping (avoid cold drops) = negligible
                                  ─────────
Warm pool monthly fixed overhead =  $525.60 / month
```

This is a hard floor we pay regardless of traffic. It is the price we charge ourselves for the **interactive** SLA tier. Everything else (cold path, cron-triggered jobs) bills only when running.

**Per-user-per-month, blended (assumes ~30 turns/user/month, ~400 output tokens/turn):**

| Tier        | Active users | Warm-pool floor | Variable (Σ tokens) | Blended $/user/mo |
|-------------|--------------|-----------------|---------------------|-------------------|
| 100 users   | 100          | $525.60         | ~$0.96              | **~$5.27**        |
| 1,000 users | 1,000        | $525.60         | ~$9.60              | **~$0.54**        |
| 10,000 users| 10,000       | $525.60 × 2*    | ~$96.00             | **~$0.12**        |

\*At 10k users we'd run 2 warm instances behind a load-balancer rule. The floor amortizes brutally well — this is exactly why scale-to-zero with one warm pool is the right shape.

---

## 6. Scale-to-zero strategy

Two Cloud Run services for the brain, fronted by a single Cloud Run HTTP load balancer with header-based routing:

| Service              | min | max | Billing            | Routes                                   |
|----------------------|-----|-----|--------------------|------------------------------------------|
| `gemma-brain-hot`    | 1   | 4   | CPU always allocated | Discord interactions, known-operator IDs |
| `gemma-brain-cold`   | 0   | 20  | Request-based       | Web anon, batch, scheduled jobs          |

**Routing rule:** the gateway sets an `X-Mercury-Tier: interactive|balanced|batch` header. Cloud Load Balancing inspects it and steers `interactive` to the hot service, everything else to the cold one. The hot service runs E4B only; the cold one runs 26B MoE by default and 31B on `?model=31b`.

**Cron warm-ping.** Cloud Scheduler hits the hot brain's `/healthz` every 4 minutes between 08:00–02:00 America/Chicago. This is shorter than Cloud Run's idle-eviction window for `min=1` services (which already keeps the instance alive) but it doubles as a synthetic check — if the ping fails, alert fires before a real user hits a cold instance.

**Cold-start budget.** The cold service ships with the 26B MoE weights baked into the container image (16 GB → 8 GB after on-disk quantization to int4). Cold start: ~8 s including container pull, GPU attach, model load, and first-token TTFT. Acceptable under the **balanced** SLA; users are told to expect "thinking…" up to 8 s.

---

## 7. Latency tiers

| Tier         | First-token SLA | Path                                   | Model         | Use cases                          |
|--------------|-----------------|----------------------------------------|---------------|------------------------------------|
| interactive  | < 2 s           | Hot pool, vLLM, no thinking            | Gemma 4 E4B   | Discord chat, slash commands       |
| balanced     | < 8 s           | Cold start OK; fast pass + opt long    | Gemma 4 26B MoE | Web chat, analysis, planning     |
| batch        | < 60 s          | Scale-to-zero, full thinking, multimodal | Gemma 4 31B | `/think` deep reasoning, fMRI summary |

The gateway picks the tier from a small set of signals: Discord interactions are interactive by default; `/think` and `/research` slash commands escalate to batch; web anon traffic is forced to balanced + cold. Users can override with `--tier batch` in the CLI surface.

---

## 8. fMRI upload pipeline

| Step | Surface         | Action                                                                                  | Storage                                                  |
|------|-----------------|-----------------------------------------------------------------------------------------|----------------------------------------------------------|
| 1    | Discord         | User runs `/upload-fmri`                                                                | —                                                        |
| 2    | Gateway         | Generates V4 signed URL, 15 min TTL, single-use, `x-goog-content-encoding` enforced     | Signed URL has prefix `gs://cortex-fmri-uploads/{discord_id}/{scan_id}/` |
| 3    | Discord         | Bot DMs the user the URL + a one-page `/upload` web form that POSTs directly to GCS     | —                                                        |
| 4    | Browser         | User uploads NIfTI / DICOM / BIDS / .nii.gz / .mat / EDF                                | GCS, CMEK + per-user KMS key                             |
| 5    | GCS             | `object.finalize` → Pub/Sub topic `cortex-fmri-finalize`                                | —                                                        |
| 6    | Cloud Function  | `cortex-fmri-validator` runs: NIfTI header check, DICOM tag scan, BIDS structure, PHI sweep | —                                                    |
| 7    | Firestore       | On valid: write `users/{discord_id}/fmri_scans/{scan_id}` with format/TR/dims/consent   | `consent.train_optin = false` until user confirms        |
| 8    | Discord         | Bot DMs the user with verdict + a button that flips `train_optin` to true               | —                                                        |
| 9    | GCS lifecycle   | 30-day soft-delete grace; 1-year retention if `train_optin == true`; else delete at 30d | —                                                        |

**Validation rules** (the function rejects with a Discord DM explaining why):

- NIfTI: orientation matrix non-singular, voxel size finite, dim ≤ 256³, TR in [0.5, 5.0] s
- DICOM: zero PHI in tags 0010,xxxx (PatientName, PatientID, PatientBirthDate, etc.) — auto-strip if present, log the strip event
- BIDS: must contain `dataset_description.json`; subject IDs hashed to `sub-{sha256[:8]}`
- Generic: file size ≤ 4 GB; one scan = one upload

---

## 9. Training pipeline

A Cloud Scheduler cron runs `cortex-train-trigger` daily at 04:00 America/Chicago. It queries Firestore for `count(fmri_scans where train_optin = true and not used_in_train_run)` and triggers a retrain when count ≥ N (default 50, configurable). The trigger function decides where to run:

```python
# pseudocode
util = http.get("https://cortex.redteamkitchen.com/api/utilization", timeout=5)
if util.ok and util.accepting and not util.tribe_active and util.free_vram_gb > 24:
    # Local 5090 path — preferred, free at margin
    cloud_tasks.enqueue("cortex-train-local", payload={"run_id": run_id})
else:
    # Vertex AI path — managed, costs money
    vertex.create_custom_training_job(
        machine="a2-highgpu-8g",            # 8× A100 40GB, $33.07/hr managed
        spot=True,                           # → ~$9.92/hr; tolerate preemption
        worker_pool=tribe_v2_train_image,
        args=["--run-id", run_id, "--scans-bucket", "cortex-fmri-uploads"],
        artifact_uri=f"gs://cortex-tribe-models/{run_id}/",
    )
```

**Smoke-test gating.** After the training job writes weights, a `cortex-train-smoketest` Cloud Run job loads the new TRIBE v2, runs inference on a held-out 30-second clip, and compares against the previous version's prediction on the same clip. If the MSE delta on the canonical Schaefer-400 parcellation is within tolerance (default ±15% per-network), the new weights are promoted by writing `gs://cortex-tribe-models/current/` as a copy. Otherwise the run is flagged for human review and a Discord webhook fires.

Promotion triggers:
- Local 5090 picks up the new weights at next idle window via a watcher script.
- Cloud Run `cortex-tribe-worker` redeploys with the new GCS pointer baked in (Cloud Build).
- Each contributor gets a Discord DM: *"TRIBE v2 has been updated to revision {short_sha}. Your scan was one of {N} that contributed."*

---

## 10. Resilience + automation

| Component                  | Health check                              | Failure mode                                   |
|----------------------------|-------------------------------------------|------------------------------------------------|
| `mercury-gateway`          | `/healthz` every 60 s                     | Cloud Run restarts; alert at 3 consecutive fails |
| `gemma-brain-hot`          | Warm-ping every 4 min                     | Auto-restart + page operator on cold-instance hit |
| `gemma-brain-cold`         | First-request synthetic                   | Cold-start metric → alert if p99 > 12 s        |
| `cortex-fmri-validator`    | Pub/Sub DLQ after 5 retries               | Failed messages → Firestore `_quarantine/`     |
| Vertex AI training job     | Built-in retry (≤3) + checkpointing       | On exhaustion, alert + queue manual replay     |
| Local 5090 path            | `/api/utilization` polled every minute    | Auto-fallover to cloud; alert after 10 min down |
| Daily cost report          | Cloud Scheduler 09:00 CT                  | Discord webhook posts yesterday's spend by SKU |
| Budget alerts              | $50 / $200 / $500 / $1000 cumulative      | Discord webhook + email; $1000 = hard cap      |

All operator alerts route to a single Discord webhook in the `#mercury-ops` channel. The webhook URL lives in Secret Manager; rotation is a one-touch IAM swap.

---

## 11. Privacy posture

fMRI data is sensitive. It is also, in our case, **not strictly HIPAA-covered** — there is no clinical metadata, no provider relationship, no diagnosis, and no minimum-necessary access from a covered entity. We are a research-grade voluntary upload portal, not a medical record system.

Defaults we ship:

- **Default consent: read-only by uploader.** `consent.train_optin = false` until the user clicks a button in Discord.
- **Per-user encryption.** Cloud KMS key per `discord_id`. Revoking the key cryptographically forecloses recovery.
- **K-anonymous re-encryption sweep.** When a user revokes, a Cloud Function re-encrypts any remaining contributions to the *training corpus* under the corpus-level key and removes their per-user pointer — leaving the contribution in aggregate but unlinkable.
- **No PHI ingestion.** DICOM tag scrubber rejects on PHI presence by default; the user is told to upload a de-identified version.
- **Egress controls.** Bucket has `requestorPays=false` and `uniformBucketLevelAccess=true`. No public URLs, ever — every read goes through a signed URL or service-account-authenticated fetch.

---

## 12. Open questions

These are decisions we cannot make from the prompt alone.

1. **Brain runtime: vLLM or Ollama?** vLLM is OpenAI-compatible out of the box and ~30% faster on E4B at our token sizes — but as of writing it does not support Gemma 4's multimodal vision tower. Ollama supports Gemma 4 multimodal but is single-stream and slower. Do we ship two runtimes (vLLM for E4B text-only hot, Ollama for 26B MoE multimodal cold), or wait for vLLM multimodal support?
2. **Region.** We default to `us-central1` (cheapest L4 + closest to Chicago). Does ABM × ISU need an EU mirror for European fMRI contributors, or is one region with signed URLs acceptable?
3. **Discord-only auth.** Some research collaborators don't have Discord accounts. Do we add Google OAuth as a second identity (and merge by verified email), or stay strictly Discord-first to keep the UX simple?
4. **Retrain cadence.** We default to N=50 opted-in scans before triggering a retrain. Is that the right threshold for ISU's protocol, or should it be time-based (monthly) regardless of count?
5. **fMRI consent flow.** The button-in-Discord pattern works for the modal user, but for clinical-adjacent collaborators we may want a signed PDF consent form. Do we build that in, or punt to "talk to us if you need it"?

---

*Last updated: May 2026. Status: planning. Next step: stand up `gemma-brain-cold` Cloud Run service + Firestore rules + Discord OAuth flow, in that order.*
