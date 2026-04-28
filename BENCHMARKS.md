# Mercury Benchmarks

Measured numbers for the Mercury fork on the reference hardware. All
values are wall-clock, single-shot (no caches warmed except where noted),
on the canonical RTX 5090 desktop (Windows 11, 64 GB DDR5).

## Reference Hardware

| Component | Spec |
|---|---|
| GPU | NVIDIA RTX 5090 (32 GB GDDR7, Blackwell sm_120) |
| CPU | (existing, undisclosed for this benchmark) |
| RAM | 64 GB DDR5 |
| OS | Windows 11 |
| Python | 3.12 |
| Torch | 2.12.0.dev20260408+cu128 |

## CLI Cold-Start

| Action | Wall-clock |
|---|---:|
| `mercury --version` | < 0.5 s |
| `mercury skills list` | < 1.0 s |
| `mercury -z "..." --provider nous-portal --model moonshotai/kimi-k2.6` (single-turn, network round-trip) | 2–4 s |
| `tools/dashboard.py --statusline` (every Claude Code turn) | **129 ms** |

## Inference Round-Trip (Nous Portal, this submission's primary path)

Measured from `tools/kimi_dispatch.py` self-test on `Kimi K2.6` via Nous
Portal Plus tier. Spec: 230 chars in.

| Phase | Value |
|---|---:|
| Network RTT to `inference-api.nousresearch.com` | ~80 ms |
| Time to first token (TTFT) | ~600 ms |
| Output rate (steady-state) | ~150 tok/s |
| **End-to-end for a 269-in / 319-out task** | **~3.2 s** |
| **Cost per task** | **$0.0015** |

Cost-per-task scales linearly with output tokens. A typical brain-viz
implementation skill build (3K in / 8K out) runs ~10 s and costs ~$0.04.

## Local Inference (Gemma 4 via Ollama)

| Model | VRAM | Throughput | Notes |
|---|---:|---:|---|
| `gemma4:e4b` (Q4_K_XL) | ~5 GB | 196 tok/s | Mercury's "fast" tier |
| `gemma4:26b` (Q4_K_M) | ~17 GB | 132 tok/s | Default narration model |
| `gemma4:31b` (Q4_K_M) | ~19 GB | 96 tok/s | Higher-quality narration |
| `embeddinggemma:300m` | 1.1 GB | 800 emb/s | RAG / memory queries |

GPU swap by Cortex's scheduler: Gemma 4 26B unload + TRIBE v2 22 GB load
takes ~12 s. Reverse: ~6 s.

## Brain Pipeline (Cortex, the brain backend)

| Stage | Time | What's happening |
|---|---:|---|
| `media_gate` (Gemma 4 E4B vision check) | 0.8–1.5 s | Per-clip safety + content classification |
| Gemma → TRIBE swap | ~12 s | GPU eviction, weight load, torch.compile |
| TRIBE v2 forward pass (50-s clip) | 4–6 min | 100 timepoints × 20,484 vertices |
| `narrate` (3 tiers) | ~30 s total | Gemma 4 26B, three sequential calls |
| Three.js page first paint | 200–400 ms | After scan complete; depends on browser |
| **Total — 50-s video to viewable page** | **~5–7 min** | Dominated by TRIBE inference |

For the Nous demo, pre-compute one canonical scan ahead of recording so the
"watch the bar fill in real-time" segment doesn't need a fresh TRIBE pass.

## fmri-overlay Render Performance (mercury-web)

| Mesh | Timepoints | Frame time | FPS at 4K |
|---|---:|---:|---:|
| fsaverage5 pial (20,484 verts) | 100 | < 1.0 ms | 240+ |
| fsaverage5 pial | 600 | < 1.2 ms | 240+ |
| fsaverage6 pial (40,962 verts) | 100 | < 1.5 ms | 200+ |
| fsaverage6 pial | 600 | < 1.8 ms | 180+ |

GPU work is dominated by texture upload, not draw calls. With the
`Data3DTexture` approach, frame cost is independent of timepoint count up
to GPU memory limits.

## Data Pipeline (LanceDB embeddings, the related JennyOfOldstones project)

For reference, since the same Mercury host runs both. From the dashboard:

| Table | Rows | Dim | Source |
|---|---:|---:|---|
| `messages_g2` | 231,634 | 3,072 | Gemini Embedding 2 over 87,543 distinct messages |
| `windows_g2` | 150,578 | 3,072 | 5-message conversation windows |
| `photos_g2` | 935 | 3,072 | Photo embeddings with vision-described context |
| `messages` (legacy) | 328,105 | 768 | Local `embeddinggemma:300m` baseline |

Total inference cost across all three Gemini-2 tables: **~$2.50** (no markup,
direct Google Cloud billing).

## Model Comparison Matrix (this submission's relevant axes)

| Capability | Kimi K2.6 | Hermes 4 405B | Gemma 4 31B (local) | Notes |
|---|---|---|---|---|
| SWE-Bench Pro | **58.6%** (#1 open-weight) | n/a | n/a | Why Kimi is the default coder |
| GPQA Diamond | 84.5 | comparable | n/a | Reasoning escalation either works |
| MMLU-Pro | 81.1 | higher | mid-tier | |
| Context length | 256 K | 131 K | 128 K | Kimi for whole-codebase prompts |
| Native function-calling | yes | yes (Nous's flagship) | indirect (via prompts) | Hermes 4 wins for the agent loop |
| Cost (per 1M tokens, in/out) | $0.95 / $4.00 | included in Nous Plus | $0 (local) | |
| Privacy / offline | API call | API call | **on-device** | Why Gemma 4 stays for the brain pipeline narration |

## How These Numbers Were Captured

```bash
# CLI cold-start
time "C:/Users/soumi/mercury/.venv/Scripts/mercury.exe" --version

# Inference round-trip
python tools/kimi_dispatch.py --task .smoke_spec.md --max-tokens 200

# Status-line latency
time "C:/Users/soumi/AppData/Local/Programs/Python/Python312/python.exe" \
     C:/Users/soumi/JennyOfOldstones/tools/dashboard.py --statusline

# Local inference
ollama run gemma4:e4b "explain photosynthesis" --verbose

# fmri-overlay frame time (mercury-web with React DevTools profiler)
# See mercury-web/perf/cortex-overlay.bench.tsx
```

Numbers will drift with model updates and torch nightlies. Rerun the
benchmarks before any tagged release.

— measured for the Nous Research Hermes Agent Creative Hackathon submission, Apr 2026
