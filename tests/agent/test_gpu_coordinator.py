"""Unit tests for the Cortex GPU-coordinator decision matrix."""
from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from agent.gpu_coordinator import (
    CortexUnreachable,
    GpuCoordinator,
    GpuVerdict,
    _decide_from_utilization,
)


def _payload(state: str, free_gb: float, total_gb: float = 32.0) -> dict:
    return {
        "accepting": True,
        "queue_depth": 0,
        "running": 0,
        "max_queue": 8,
        "scheduler_state": "idle",
        "vram": {
            "state": state,
            "total_gb": total_gb,
            "used_gb": total_gb - free_gb,
            "free_gb": free_gb,
            "tribe_fits": free_gb >= 22.4,
            "gemma_e4b_fits": free_gb >= 10.0,
        },
    }


# --- decision matrix ----------------------------------------------------


def test_idle_with_full_vram_picks_largest_fit():
    v = _decide_from_utilization(_payload("idle", free_gb=26.0), requested=None)
    assert v.can_run
    # 22GB model fits in 26-1=25 budget; bigger ones don't exist in the matrix
    assert v.recommended_model == "gemma4:31b"


def test_idle_can_run_explicit_request_when_it_fits():
    v = _decide_from_utilization(_payload("idle", free_gb=26.0), requested="gemma4:e4b")
    assert v.can_run
    assert v.recommended_model == "gemma4:e4b"


def test_idle_downgrades_when_request_exceeds_budget():
    # 12GB free with a 1GB safety margin = 11GB budget -> e4b (10) fits
    v = _decide_from_utilization(_payload("idle", free_gb=12.0), requested="gemma4:31b")
    assert v.can_run
    assert v.recommended_model == "gemma4:e4b"
    assert "downgrad" in v.reason.lower()


def test_gemma_active_recommends_reuse():
    v = _decide_from_utilization(_payload("gemma_active", free_gb=16.0), requested=None)
    assert v.can_run
    assert v.recommended_model == "gemma4:e4b"
    assert "reuse" in v.reason.lower()


def test_tribe_active_only_4b_fits():
    v = _decide_from_utilization(_payload("tribe_active", free_gb=6.0), requested="gemma4:e4b")
    assert v.can_run
    assert v.recommended_model == "gemma4:4b"


def test_tribe_active_with_no_room_blocks():
    v = _decide_from_utilization(_payload("tribe_active", free_gb=2.0), requested=None)
    assert not v.can_run
    assert v.recommended_model is None
    assert v.wait_seconds and v.wait_seconds > 0


def test_swapping_blocks_with_wait():
    v = _decide_from_utilization(_payload("swapping", free_gb=0.0), requested=None)
    assert not v.can_run
    assert v.wait_seconds == 10


def test_unknown_model_passes_through_when_idle():
    v = _decide_from_utilization(_payload("idle", free_gb=20.0), requested="gemma4:future")
    assert v.can_run
    assert v.recommended_model == "gemma4:future"


# --- caching + HTTP fallback -------------------------------------------


def test_cortex_unreachable_assumes_idle():
    coord = GpuCoordinator(cortex_url="http://127.0.0.1:1")
    with patch("agent.gpu_coordinator.requests.get", side_effect=requests.ConnectionError("nope")):
        v = coord.decide()
    assert v.can_run
    assert "unreachable" in v.reason.lower()
    assert v.recommended_model == "gemma4:e4b"


def test_cache_avoids_repeat_http_calls():
    coord = GpuCoordinator(cache_ttl=60.0)
    fake = _MockResponse(_payload("idle", free_gb=26.0))
    with patch("agent.gpu_coordinator.requests.get", return_value=fake) as mock_get:
        coord.decide()
        coord.decide()
        coord.decide()
    assert mock_get.call_count == 1


def test_cache_invalidate_forces_refresh():
    coord = GpuCoordinator(cache_ttl=60.0)
    fake = _MockResponse(_payload("idle", free_gb=26.0))
    with patch("agent.gpu_coordinator.requests.get", return_value=fake) as mock_get:
        coord.decide()
        coord.invalidate()
        coord.decide()
    assert mock_get.call_count == 2


def test_invalid_json_treated_as_unreachable():
    coord = GpuCoordinator()
    fake = _MockResponse({}, raises_json=True)
    with patch("agent.gpu_coordinator.requests.get", return_value=fake):
        v = coord.decide()
    assert v.can_run
    assert "unreachable" in v.reason.lower()


# --- helpers -----------------------------------------------------------


class _MockResponse:
    def __init__(self, payload: dict, raises_json: bool = False, status: int = 200):
        self._payload = payload
        self._raises_json = raises_json
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self) -> dict:
        if self._raises_json:
            raise ValueError("bad json")
        return self._payload


# --- structural sanity --------------------------------------------------


def test_verdict_dataclass_shape():
    v = GpuVerdict(can_run=True, recommended_model="gemma4:e4b", reason="x", wait_seconds=None)
    assert v.can_run is True
    assert v.recommended_model == "gemma4:e4b"
    assert v.wait_seconds is None


def test_cortex_unreachable_is_exception():
    with pytest.raises(CortexUnreachable):
        raise CortexUnreachable("boom")
