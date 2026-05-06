# Mercury end-to-end demo — 2026-05-06T19:28:50Z

## TUI: `mercury -z`

### Prompt

```
In one sentence, why does running Gemma 4 locally on consumer hardware matter for digital equity?
```

### Response

```
Running models like Gemma 4 locally on consumer hardware democratizes access to advanced AI capabilities by removing reliance on centralized cloud APIs, thereby mitigating paywalls, rate limits, and internet dependency which perpetuate digital divides.
```


---

## Public MTP at `inference.redteamkitchen.com`

### Wall time: 0.31s

### Response

```
Mercury MTP live.
```

### Usage

```json
{
  "prompt_tokens": 24,
  "completion_tokens": 6,
  "total_tokens": 30,
  "prompt_tokens_details": {
    "cached_tokens": 0
  },
  "prompt_tps": 0.0,
  "generation_tps": 0.0,
  "peak_memory": 6.942381218
}
```


---

## Cortex backend `/api/health`

```json
{
  "ok": true,
  "version": "0.1.0",
  "gpu": {
    "state": "idle",
    "device_kind": "cuda",
    "device_name": "NVIDIA GeForce RTX 5090",
    "total_gb": 34.19,
    "used_gb": 15.21,
    "free_gb": 16.22,
    "tribe_fits": true,
    "gemma_e4b_fits": true,
    "swap_metrics": {
      "total_swaps": 0,
      "avg_swap_time_s": 0.0,
      "oom_recoveries": 0
    }
  },
  "queue": {
    "queue_depth": 0,
    "processing": false,
    "active_request": null,
    "gpu_state": "idle",
    "completed": 0,
    "failed": 0
  },
  "websocket_clients": 0
}
```


---

## Discord (bot-test-4)

### Channel: bot-test-4 (`1501660119350644808`)

### Latest 5 messages (newest first):

- **abmsnowy [BOT]** @ 2026-05-06T19:28:30
  ```
  --- E2E DEMO MARKER 2026-05-06T19:28:29Z ---
  ```
- **abmsnowy [BOT]** @ 2026-05-06T19:27:39
  ```
  e2e demo test
  ```
- **omlahiri** @ 2026-05-06T19:09:11
  ```
  <@1335430089671970837>  What model variants of Gemma 4 are most efficient for local deployment, and which one would you recommend for a teacher running it on a MacBook with 16GB RAM? Keep it concise.
  ```
- **abmsnowy [BOT]** @ 2026-05-06T19:08:51
  ```
  @Snowy What model variants of Gemma 4 are most efficient for local deployment, and which one would you recommend for a teacher running it on a MacBook with 16GB RAM? Keep it concise.
  ```
- **abmsnowy [BOT]** @ 2026-05-06T19:08:00
  ```
  --- AFTER: same response through the new Discord formatter ---
  > 👁️ `vision_analyze` · "What is the main topic of the post, a..."
  
  The main topic is the Gemma 4 Model Update, specifically the new chat template Google released.
  ```


---

## Infrastructure snapshot

### Heartbeat

```json
{
  "total": 10,
  "ok": 10,
  "down": []
}
```

### Gaming state

```json
{
  "gaming": false,
  "preferred_provider": "ollama-local",
  "running_games": [],
  "failover_reason": "idle"
}
```

### OpenRouter daily quota

```json
{
  "date": null,
  "free_used": null,
  "paid_usd": null
}
```


---

## Demo screenshots

- `D1_cortex_demo.png` (384 KB) — http://localhost:5173
- `D2_mercury_dashboard.png` (283 KB) — http://localhost:9119
- `D3_inference_models.png` (95 KB) — https://inference.redteamkitchen.com/v1/models
- `D4_cortex_health.png` (49 KB) — http://localhost:8773/api/health
- `D5_mercury_subdomain.png` (283 KB) — https://mercury.redteamkitchen.com

---

