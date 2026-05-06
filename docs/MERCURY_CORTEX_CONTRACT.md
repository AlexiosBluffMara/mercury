# Mercury × Cortex contract

**Updated:** 2026-05-06

Mercury and Cortex share a single 32 GB RTX 5090 on Seratonin. Cortex owns the GPU swap state machine; Mercury defers to it before loading models into Ollama.

## The contract — one HTTP endpoint

Cortex exposes `GET /api/utilization` at `http://localhost:8773`. Mercury polls it before any Gemma load, with a 5s cache TTL.

### Response schema

```json
{
  "accepting": true,
  "queue_depth": 0,
  "running": 0,
  "max_queue": 8,
  "scheduler_state": "idle",
  "vram": {
    "state": "idle",
    "device_kind": "cuda",
    "device_name": "NVIDIA GeForce RTX 5090",
    "total_gb": 34.19,
    "used_gb": 4.69,
    "free_gb": 26.74,
    "tribe_fits": true,
    "gemma_e4b_fits": true,
    "swap_metrics": {
      "total_swaps": 0,
      "avg_swap_time_s": 0.0,
      "oom_recoveries": 0
    }
  }
}
```

### `scheduler_state` values

| State | Meaning | Mercury action |
|---|---|---|
| `idle` | nothing loaded, fresh load OK | proceed; pick model fitting `vram.free_gb` |
| `gemma_active` | a Gemma variant is warm | reuse the warm one (Mercury must read which) |
| `tribe_active` | TRIBE v2 is generating | refuse; return wait suggestion ~30s |
| `swapping` | mid-swap in/out | refuse; return wait suggestion ~3s |

### Mercury's selection logic

`agent/gpu_coordinator.py:GpuCoordinator.decide()` returns a `GpuVerdict`:

- `can_run` — boolean
- `recommended_model` — `gemma4:31b` / `gemma4:27b` / `gemma4-26b-moe` / `gemma4:e4b` / `gemma4:4b`, picked **largest first** that fits in `vram.free_gb − VRAM_SAFETY_MARGIN_GB (1 GB)`
- `reason` — human-readable string for logs
- `wait_seconds` — populated when `can_run=False` and a retry is reasonable

### Failure mode: Cortex unreachable

When `requests.get(url, timeout=2.0)` raises (port 8773 down), `GpuCoordinator` does NOT block — it logs a warning and returns:

```python
GpuVerdict(can_run=True, recommended_model=None,
           reason="cortex unreachable; defaulting to idle assumption")
```

Mercury then proceeds with whatever model the user requested. This is the explicit graceful-degradation contract: **Cortex availability is informational, not gating.**

### Override knobs

- `CORTEX_URL` env var — point Mercury at a non-default Cortex (e.g. `http://100.108.253.83:8773` for Big Apple-side Mercury talking to Seratonin Cortex over Tailscale)
- `--ignore-gpu-coordinator` flag on `mercury chat` — skip the check entirely; useful when running Mercury and Cortex on different machines

## Verification (today)

```bash
$ curl -s http://localhost:8773/api/utilization | jq
{
  "scheduler_state": "idle",
  "vram": {
    "state": "idle",
    "free_gb": 26.74,
    "gemma_e4b_fits": true
  }
}

$ python3 -c "from mercury.agent.gpu_coordinator import get_coordinator; \
              c = get_coordinator(); print(c.decide())"
GpuVerdict(can_run=True, recommended_model='gemma4:31b',
           reason='free_gb=26.74 fits gemma4:31b (footprint 22 GB + 1 GB margin)',
           wait_seconds=None)
```

Both endpoints respond. The contract is live.

## What writes to the lights

When Mercury starts a generation, `agent/run.py:_lights_fire('mercury-start')` calls the WSL2 daemon at `/mnt/d/cortex/lights/state-update.sh`. The daemon flips `~/.cortex/lights-state.json:mercury_active` to `true`. The Hue daemon (`D:\cortex\lights\lights.py` watching that file's mtime) drives the bulbs to green within ~250 ms.

Cortex does the same on its own job start/stop. If both are active, lights stay green. The state machine is at `~/.claude/skills/ascended-base-lights/SKILL.md`.

## Why this contract is the right shape

1. **One endpoint, one cache** — no protobuf, no GRPC, no shared library. Just curl-able JSON.
2. **Cortex owns the GPU state machine** — Mercury never tries to second-guess the swap; it just asks "is now OK?" and either proceeds or backs off.
3. **Graceful degradation** — Cortex being down doesn't take Mercury offline. Mercury logs a warning and trusts the user's request.
4. **No bidirectional coupling** — Cortex doesn't import Mercury and doesn't know it exists. Mercury imports `cortex_bridge` only as a thin HTTP client.
5. **Small surface = small bug surface** — six fields in the JSON, four enum states, one cache TTL. Easy to mock in tests.

## Files

- `D:\mercury\agent\gpu_coordinator.py` — Mercury side. Polls Cortex, caches 5s, emits `GpuVerdict`.
- `D:\mercury\mercury\cortex_bridge.py` — thin `cortex_vram_report()` wrapper exposed to Mercury skills.
- `D:\cortex\cortex\server.py` — Cortex side. FastAPI route `/api/utilization` (port 8773).
- `D:\cortex\cortex\job_scheduler.py` — Cortex's actual scheduler that produces the state.
- `D:\cortex\lights\lights.py` — Hue daemon, watches `~/.cortex/lights-state.json` mtime.
