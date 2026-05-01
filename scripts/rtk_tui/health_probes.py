"""Async pollers for tunnel state, GPU state, and service status.

Each probe returns a small dataclass — the TUI renders them, the health
monitor decides whether to alert and restart.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass, field

import httpx

CORTEX_URL = "http://localhost:8765"
MERCURY_URL = "http://localhost:8767"   # mercury gateway internal HTTP API
TUNNEL_NAME = "rtk-5090"


@dataclass
class TunnelInfo:
    name: str = TUNNEL_NAME
    connections: int = 0
    healthy: bool = False
    detail: str = ""


@dataclass
class GpuState:
    available: bool = False
    vram_free_mb: int | None = None
    vram_total_mb: int | None = None
    scheduler_state: str = "unknown"
    queue_depth: int | None = None
    detail: str = ""


@dataclass
class HttpHealth:
    url: str
    ok: bool = False
    status_code: int | None = None
    detail: str = ""


@dataclass
class ProbeBundle:
    tunnel: TunnelInfo = field(default_factory=TunnelInfo)
    gpu: GpuState = field(default_factory=GpuState)
    cortex: HttpHealth = field(default_factory=lambda: HttpHealth(url=f"{CORTEX_URL}/api/health"))
    mercury: HttpHealth = field(default_factory=lambda: HttpHealth(url=f"{MERCURY_URL}/api/health"))


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

async def probe_tunnel(name: str = TUNNEL_NAME) -> TunnelInfo:
    """Run ``cloudflared tunnel info <name>`` and parse connection count.

    Falls back to a "missing binary" state if cloudflared isn't on PATH.
    """
    info = TunnelInfo(name=name)
    if not shutil.which("cloudflared"):
        info.detail = "cloudflared not on PATH"
        return info

    try:
        proc = await asyncio.create_subprocess_exec(
            "cloudflared", "tunnel", "info", "--output", "json", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    except (asyncio.TimeoutError, FileNotFoundError) as exc:
        info.detail = f"timeout/error: {exc}"
        return info

    if proc.returncode != 0:
        info.detail = (stderr.decode(errors="replace") or "non-zero exit").strip().splitlines()[-1]
        return info

    try:
        payload = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError:
        info.detail = "could not parse cloudflared output"
        return info

    # cloudflared json shape: {"id":..., "conns":[{...}, ...]}
    conns = payload.get("conns") or payload.get("connections") or []
    info.connections = len(conns)
    info.healthy = info.connections > 0
    info.detail = f"{info.connections} connection(s)"
    return info


async def probe_gpu(client: httpx.AsyncClient) -> GpuState:
    """Poll the cortex utilization endpoint for live GPU state."""
    state = GpuState()
    try:
        resp = await client.get(f"{CORTEX_URL}/api/utilization", timeout=3.0)
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        state.detail = f"unreachable: {exc.__class__.__name__}"
        return state

    if resp.status_code != 200:
        state.detail = f"HTTP {resp.status_code}"
        return state

    try:
        data = resp.json()
    except ValueError:
        state.detail = "non-JSON response"
        return state

    state.available = True
    state.vram_free_mb = data.get("vram_free_mb")
    state.vram_total_mb = data.get("vram_total_mb")
    state.scheduler_state = data.get("scheduler_state", "unknown")
    state.queue_depth = data.get("queue_depth")
    return state


async def probe_http(client: httpx.AsyncClient, url: str) -> HttpHealth:
    h = HttpHealth(url=url)
    try:
        resp = await client.get(url, timeout=3.0)
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        h.detail = f"{exc.__class__.__name__}"
        return h
    h.status_code = resp.status_code
    h.ok = 200 <= resp.status_code < 300
    if not h.ok:
        h.detail = f"HTTP {resp.status_code}"
    return h


async def gather_all(client: httpx.AsyncClient) -> ProbeBundle:
    tunnel, gpu, cortex, mercury = await asyncio.gather(
        probe_tunnel(),
        probe_gpu(client),
        probe_http(client, f"{CORTEX_URL}/api/health"),
        probe_http(client, f"{MERCURY_URL}/api/health"),
    )
    return ProbeBundle(tunnel=tunnel, gpu=gpu, cortex=cortex, mercury=mercury)


# ---------------------------------------------------------------------------
# Synchronous wrappers (used by the health monitor cron job)
# ---------------------------------------------------------------------------

def sync_tunnel(name: str = TUNNEL_NAME) -> TunnelInfo:
    """Blocking variant: convenient for cron scripts that don't want asyncio."""
    if not shutil.which("cloudflared"):
        return TunnelInfo(name=name, detail="cloudflared not on PATH")
    try:
        result = subprocess.run(
            ["cloudflared", "tunnel", "info", "--output", "json", name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return TunnelInfo(name=name, detail=str(exc))

    if result.returncode != 0:
        return TunnelInfo(name=name, detail=(result.stderr or "non-zero exit").strip()[:200])

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return TunnelInfo(name=name, detail="could not parse cloudflared output")

    conns = payload.get("conns") or payload.get("connections") or []
    return TunnelInfo(
        name=name,
        connections=len(conns),
        healthy=len(conns) > 0,
        detail=f"{len(conns)} connection(s)",
    )


def sync_http(url: str, timeout: float = 3.0) -> HttpHealth:
    h = HttpHealth(url=url)
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        h.detail = f"{exc.__class__.__name__}"
        return h
    h.status_code = resp.status_code
    h.ok = 200 <= resp.status_code < 300
    if not h.ok:
        h.detail = f"HTTP {resp.status_code}"
    return h
