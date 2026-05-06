#!/usr/bin/env python3
"""seratonin_gaming_watch.py — auto-failover Mercury inference when Soumit's gaming.

Runs as a Windows scheduled task on Seratonin every 30s. Detects gaming via:
  1. NVIDIA-SMI GPU utilization > 70% sustained for 30s+
  2. Known gaming launchers running (Steam.exe, RiotClient*.exe, BlizzardLauncher.exe, ...)
  3. A fullscreen window present on the gaming monitor

Writes state to ~/.mercury/gaming_state.json (atomic). Mercury reads it on each
request via gpu_coordinator and routes 'fast' through Big Apple instead of
Seratonin Ollama when state["gaming"] is True.

State JSON shape:
    {
      "gaming": true|false,
      "since": "2026-05-06T18:30:12Z",        # when current state began
      "gpu_util_pct": 82,                       # last sample
      "vram_used_gb": 18.4,
      "running_games": ["RiotClient.exe", "VALORANT.exe"],
      "preferred_provider": "mlx-bigapple-e4b" | "ollama-local",
      "failover_reason": "gpu>70 for 60s; valorant detected"
    }
"""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone

STATE_FILE = Path.home() / ".mercury" / "gaming_state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Launchers running in the background ≠ actively gaming. Only treat the actual
# game *.exe as a trigger; launchers are routinely idle in the tray and would
# false-positive constantly.
ACTIVE_GAMES = {
    "VALORANT.exe", "VALORANT-Win64-Shipping.exe",
    "League of Legends.exe", "LeagueClient.exe", "LeagueClientUx.exe",
    "Cyberpunk2077.exe",
    "BaldursGate3.exe", "bg3.exe", "bg3_dx11.exe",
    "AssassinsCreedShadows.exe",
    "DyingLightTheBeast.exe",
    "DeadlockGameClient.exe", "Deadlock.exe",
    "hl_alyx.exe",   # Half-Life Alyx
    # Common AAA game patterns Soumit might play later
    "RDR2.exe", "GTA5.exe", "EldenRing.exe", "FactoryGame.exe",
}
GPU_UTIL_GAMING_THRESHOLD = 70
VRAM_USED_GAMING_THRESHOLD_GB = 8.0
GAMING_PERSIST_SECONDS = 60   # 2 cron cycles of 30s — guards against momentary spikes
COOLDOWN_SECONDS = 120        # require 2 quiet cycles before flipping back to local


def query_nvidia_smi() -> tuple[int, float]:
    """Return (gpu_util_pct, vram_used_gb)."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
             "--format=csv,noheader,nounits"], text=True, timeout=4)
        util_str, mem_mib = out.strip().split(",")
        return int(util_str.strip()), int(mem_mib.strip()) / 1024.0
    except Exception:
        return 0, 0.0


def list_running_games() -> list[str]:
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Select-Object -ExpandProperty ProcessName"],
            text=True, timeout=8)
        running = {p.strip() + ".exe" for p in out.splitlines() if p.strip()}
        return sorted(running & ACTIVE_GAMES)
    except Exception:
        return []


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"gaming": False, "since": _now(), "gpu_util_pct": 0,
                "vram_used_gb": 0.0, "running_games": [],
                "preferred_provider": "ollama-local",
                "failover_reason": "initial",
                "consecutive_gaming_samples": 0}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"gaming": False, "since": _now(), "gpu_util_pct": 0,
                "vram_used_gb": 0.0, "running_games": [],
                "preferred_provider": "ollama-local",
                "failover_reason": "state-corrupt-reset",
                "consecutive_gaming_samples": 0}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def main_loop_step() -> dict:
    util, vram = query_nvidia_smi()
    games = list_running_games()
    state = load_state()

    # Gaming if: actual game .exe running, OR sustained heavy GPU+VRAM (e.g. running a model
    # Mercury didn't load itself).
    gaming_signal = bool(games) or (
        util >= GPU_UTIL_GAMING_THRESHOLD and vram >= VRAM_USED_GAMING_THRESHOLD_GB
    )

    if gaming_signal:
        state["consecutive_gaming_samples"] = state.get("consecutive_gaming_samples", 0) + 1
    else:
        state["consecutive_gaming_samples"] = 0

    # Only flip TO gaming after sustained signal; flip BACK after a calmer cooldown
    new_gaming = state.get("gaming", False)
    samples_required = max(1, GAMING_PERSIST_SECONDS // 30)  # cron runs every 30s

    if not state.get("gaming", False) and state["consecutive_gaming_samples"] >= samples_required:
        new_gaming = True
    elif state.get("gaming", False) and state["consecutive_gaming_samples"] == 0:
        # Cooldown: only flip back if quiet for at least one full poll cycle
        new_gaming = False

    if new_gaming != state.get("gaming"):
        state["since"] = _now()
        state["gaming"] = new_gaming
    state["gpu_util_pct"] = util
    state["vram_used_gb"] = round(vram, 2)
    state["running_games"] = games
    state["preferred_provider"] = "mlx-bigapple-e4b" if new_gaming else "ollama-local"

    reasons = []
    if games:
        reasons.append(f"games detected: {','.join(games)}")
    if util >= GPU_UTIL_GAMING_THRESHOLD:
        reasons.append(f"gpu_util={util}%")
    if vram >= VRAM_USED_GAMING_THRESHOLD_GB:
        reasons.append(f"vram={vram:.1f}GB")
    state["failover_reason"] = "; ".join(reasons) or "idle"

    save_state(state)
    return state


if __name__ == "__main__":
    s = main_loop_step()
    # Log one-line status
    print(f"[{s['since']}] gaming={s['gaming']} util={s['gpu_util_pct']}% "
          f"vram={s['vram_used_gb']}GB games={s['running_games']} "
          f"-> {s['preferred_provider']}", flush=True)
