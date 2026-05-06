#!/usr/bin/env python3
"""infra_status.py — one-shot snapshot of Mercury's whole infrastructure state.

Reads:
  ~/.mercury/heartbeat_state.json     (provider health from heartbeat_poll.py)
  ~/.mercury/gaming_state.json        (gaming mode from seratonin_gaming_watch.py)
  ~/.mercury/openrouter_daily_quota.json  (today's free-tier usage)

Prints a compact human-readable status line + JSON blob suitable for a
Mercury dashboard widget, a Discord status command, or a cron health check.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home() / ".mercury"


def _load(name: str) -> dict | None:
    p = HOME / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def main() -> int:
    hb = _load("heartbeat_state.json") or {}
    gm = _load("gaming_state.json") or {}
    qt = _load("openrouter_daily_quota.json") or {}

    health = hb.get("summary", {})
    print(f"Mercury infra status {hb.get('ts', 'never')}")
    print(f"  providers: {health.get('ok', 0)}/{health.get('total', 0)} healthy"
          + (f" | DOWN: {','.join(health.get('down', []))}" if health.get('down') else ""))
    print(f"  gaming mode: {'ON  -> ' + gm.get('preferred_provider', '?') if gm.get('gaming') else 'off'}"
          + (f" ({gm.get('failover_reason')})" if gm.get('gaming') else ""))
    print(f"  openrouter free quota: {qt.get('free_used', 0)}/1000 used today, paid_usd={qt.get('paid_usd', 0):.4f}")

    # Per-provider detail
    if hb.get("providers"):
        print("\n  per-provider:")
        for name, p in hb["providers"].items():
            ok = "ok " if p["ok"] else "DOWN"
            print(f"    [{ok}] {name:30s} {p['status']:>4d}  {p['latency_ms']:>5d}ms")

    return 0 if not health.get('down') else 2


if __name__ == "__main__":
    raise SystemExit(main())
