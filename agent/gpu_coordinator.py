"""GPU coordination with Cortex's scheduler.

Mercury and Cortex share a single 32 GB RTX 5090. Cortex owns the swap
state machine (idle / gemma_active / tribe_active / swapping). Before
Mercury loads a Gemma model into Ollama, it checks Cortex's
``/api/utilization`` endpoint and decides:

* whether it can run anything at all right now
* which Gemma variant fits in the headroom Cortex isn't using
* if it can't run, how long to wait before retrying

When Cortex is unreachable (port 8765 not listening), Mercury assumes
idle and lets the caller proceed. The coordinator never hard-blocks on
Cortex availability — it logs a warning and degrades gracefully.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

DEFAULT_CORTEX_URL = "http://localhost:8765"
HTTP_TIMEOUT_S = 2.0
CACHE_TTL_S = 5.0

# Approximate VRAM footprints (GB) for Gemma 4 variants on a 32 GB card.
MODEL_FOOTPRINT_GB: dict[str, float] = {
    "gemma4:4b": 3.0,
    "gemma4:e4b": 10.0,
    "gemma4-26b-moe": 16.0,
    "gemma4:27b": 18.0,
    "gemma4:31b": 22.0,
}

# Preference order when a free-VRAM budget allows multiple models.
LARGEST_FIRST = ["gemma4:31b", "gemma4:27b", "gemma4-26b-moe", "gemma4:e4b", "gemma4:4b"]

VRAM_SAFETY_MARGIN_GB = 1.0


@dataclass
class GpuVerdict:
    can_run: bool
    recommended_model: str | None
    reason: str
    wait_seconds: int | None = None


class CortexUnreachable(Exception):
    pass


class GpuCoordinator:
    """Cached client for Cortex's GPU utilization endpoint."""

    def __init__(self, cortex_url: str = DEFAULT_CORTEX_URL,
                 timeout: float = HTTP_TIMEOUT_S,
                 cache_ttl: float = CACHE_TTL_S) -> None:
        self._url = cortex_url.rstrip("/")
        self._timeout = timeout
        self._cache_ttl = cache_ttl
        self._cache: dict | None = None
        self._cache_at: float = 0.0
        self._lock = threading.Lock()

    def _fetch_utilization(self) -> dict:
        with self._lock:
            now = time.monotonic()
            if self._cache is not None and (now - self._cache_at) < self._cache_ttl:
                return self._cache
            try:
                resp = requests.get(
                    f"{self._url}/api/utilization", timeout=self._timeout
                )
                resp.raise_for_status()
                payload = resp.json()
            except (requests.RequestException, ValueError) as exc:
                raise CortexUnreachable(str(exc)) from exc
            self._cache = payload
            self._cache_at = now
            return payload

    def decide(self, requested: str | None = None) -> GpuVerdict:
        """Return a verdict for whether Mercury should run a model now.

        Args:
            requested: Optional explicit model the caller wants. If set
                and it doesn't fit, the verdict downgrades or refuses.
        """
        try:
            payload = self._fetch_utilization()
        except CortexUnreachable as exc:
            logger.warning(
                "[gpu_coordinator] Cortex unreachable (%s); assuming idle", exc
            )
            return GpuVerdict(
                can_run=True,
                recommended_model=requested or "gemma4:e4b",
                reason="cortex unreachable; defaulting to idle assumption",
            )

        return _decide_from_utilization(payload, requested=requested)

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_at = 0.0


def _pick_largest_fit(free_gb: float) -> str | None:
    budget = free_gb - VRAM_SAFETY_MARGIN_GB
    for model in LARGEST_FIRST:
        if MODEL_FOOTPRINT_GB[model] <= budget:
            return model
    return None


def _decide_from_utilization(payload: dict, requested: str | None) -> GpuVerdict:
    vram = payload.get("vram", {}) or {}
    state = (vram.get("state") or payload.get("scheduler_state") or "idle").lower()
    free_gb = float(vram.get("free_gb", 0.0) or 0.0)

    if state == "swapping":
        return GpuVerdict(
            can_run=False,
            recommended_model=None,
            reason="cortex is swapping models; transient state",
            wait_seconds=10,
        )

    if state == "gemma_active":
        # Cortex already has a Gemma instance warm in Ollama. The cheapest
        # outcome is to reuse it instead of forcing a second load.
        return GpuVerdict(
            can_run=True,
            recommended_model="gemma4:e4b",
            reason="cortex has gemma_active; reuse the warm Ollama instance",
        )

    if state == "tribe_active":
        # ~22.4 GB pinned. Only the smallest Gemma fits alongside.
        budget = free_gb - VRAM_SAFETY_MARGIN_GB
        if MODEL_FOOTPRINT_GB["gemma4:4b"] <= budget:
            if requested and requested != "gemma4:4b":
                return GpuVerdict(
                    can_run=True,
                    recommended_model="gemma4:4b",
                    reason=(
                        f"tribe_active leaves only {free_gb:.1f}GB free; "
                        f"downgrading {requested} -> gemma4:4b"
                    ),
                )
            return GpuVerdict(
                can_run=True,
                recommended_model="gemma4:4b",
                reason="tribe_active; only gemma4:4b fits in remaining VRAM",
            )
        return GpuVerdict(
            can_run=False,
            recommended_model=None,
            reason=f"tribe_active and only {free_gb:.1f}GB free; nothing fits",
            wait_seconds=15,
        )

    # state == "idle" (or unknown — treat as idle but advisory)
    if requested:
        footprint = MODEL_FOOTPRINT_GB.get(requested)
        if footprint is None:
            # Unknown model: trust the caller, let Ollama enforce its own limits
            return GpuVerdict(
                can_run=True,
                recommended_model=requested,
                reason=f"idle; unknown model {requested}, deferring to ollama",
            )
        if footprint + VRAM_SAFETY_MARGIN_GB <= free_gb or free_gb <= 0:
            return GpuVerdict(
                can_run=True,
                recommended_model=requested,
                reason="idle; requested model fits",
            )
        # Requested doesn't fit — pick the largest that does
        fit = _pick_largest_fit(free_gb)
        if fit:
            return GpuVerdict(
                can_run=True,
                recommended_model=fit,
                reason=(
                    f"idle but {requested} ({footprint:.0f}GB) exceeds free "
                    f"{free_gb:.1f}GB; downgrading to {fit}"
                ),
            )
        return GpuVerdict(
            can_run=False,
            recommended_model=None,
            reason=f"idle but only {free_gb:.1f}GB free; nothing fits",
            wait_seconds=10,
        )

    # No specific request: default to E4B if we can confirm fit, else 4B
    if free_gb <= 0:
        # Cortex didn't report VRAM; assume best-case
        return GpuVerdict(
            can_run=True,
            recommended_model="gemma4:e4b",
            reason="idle; no vram report, defaulting to e4b",
        )
    fit = _pick_largest_fit(free_gb)
    if fit:
        return GpuVerdict(
            can_run=True,
            recommended_model=fit,
            reason=f"idle with {free_gb:.1f}GB free; selecting {fit}",
        )
    return GpuVerdict(
        can_run=False,
        recommended_model=None,
        reason=f"idle but only {free_gb:.1f}GB free; nothing fits",
        wait_seconds=10,
    )


# Module-level singleton — most callers want the shared cache.
_default_coordinator: GpuCoordinator | None = None
_default_lock = threading.Lock()


def get_coordinator(cortex_url: str | None = None) -> GpuCoordinator:
    global _default_coordinator
    with _default_lock:
        if _default_coordinator is None:
            _default_coordinator = GpuCoordinator(
                cortex_url=cortex_url or DEFAULT_CORTEX_URL
            )
        return _default_coordinator
