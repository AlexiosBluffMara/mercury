#!/usr/bin/env python3
"""heartbeat_poll.py — poll every Mercury inference provider, write health JSON.

Runs every 30s as a Windows scheduled task. Probes each provider's
/v1/models endpoint with a 4s timeout. Writes one row to a rolling
~/.mercury/heartbeat.jsonl log and updates a snapshot at
~/.mercury/heartbeat_state.json.

Mercury's router uses heartbeat_state.json to skip providers marked
unhealthy in the last 90s. Manual healing happens automatically when a
provider responds again.
"""
from __future__ import annotations
import json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

OUT = Path.home() / ".mercury"
OUT.mkdir(parents=True, exist_ok=True)
SNAPSHOT = OUT / "heartbeat_state.json"
LOG = OUT / "heartbeat.jsonl"

PROVIDERS = [
    # (name,                        url,                                                   timeout)
    ("ollama-local",                "http://localhost:11434/api/tags",                     4),
    ("mlx-bigapple-e4b",            "http://100.93.240.52:8080/v1/models",                 4),
    ("mlx-bigapple-26b",            "http://100.93.240.52:8081/v1/models",                 4),
    ("mlx-bigapple-31b",            "http://100.93.240.52:8082/v1/models",                 4),
    ("mlx-bigapple-e4b-mtp",        "http://100.93.240.52:8083/v1/models",                 4),
    ("mercury-dashboard",           "http://localhost:9119/v1/info",                       4),
    ("cortex-fastapi",              "http://100.93.240.52:8773/api/health",                4),
    # Public Cloudflare-tunneled endpoints (off-tailnet path)
    ("public-rtk-inference",        "https://inference.redteamkitchen.com/v1/models",      8),
    ("public-rtk-mercury",          "https://mercury.redteamkitchen.com/v1/info",          8),
    ("public-rtk-cortex",           "https://cortex.redteamkitchen.com",                   8),
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probe(name: str, url: str, timeout: int) -> dict:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mercury-heartbeat/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            elapsed_ms = int((time.time() - t0) * 1000)
            return {
                "provider": name, "url": url, "ok": True, "status": r.status,
                "latency_ms": elapsed_ms, "error": None, "ts": _now(),
            }
    except urllib.error.HTTPError as e:
        # 401/403 from Ollama HTTP API is "ok, just denied" — the service is up
        ok = e.code in (200, 301, 302, 401, 403, 404)
        return {
            "provider": name, "url": url, "ok": ok, "status": e.code,
            "latency_ms": int((time.time() - t0) * 1000),
            "error": None if ok else f"HTTP {e.code}", "ts": _now(),
        }
    except Exception as e:
        return {
            "provider": name, "url": url, "ok": False, "status": 0,
            "latency_ms": int((time.time() - t0) * 1000),
            "error": f"{type(e).__name__}: {e}", "ts": _now(),
        }


def main() -> int:
    results = [probe(name, url, t) for name, url, t in PROVIDERS]
    snapshot = {
        "ts": _now(),
        "providers": {r["provider"]: r for r in results},
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r["ok"]),
            "down": [r["provider"] for r in results if not r["ok"]],
        },
    }
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2))
    with LOG.open("a") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    s = snapshot["summary"]
    print(f"[{snapshot['ts']}] {s['ok']}/{s['total']} healthy" +
          (f" | DOWN: {','.join(s['down'])}" if s["down"] else ""))
    return 0 if not snapshot["summary"]["down"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
