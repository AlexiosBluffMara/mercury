import importlib.util
from unittest.mock import patch

import pytest

from mercury import cortex_bridge

cortex_installed = importlib.util.find_spec("cortex") is not None


def test_cortex_unavailable_when_import_fails():
    with patch("mercury.cortex_bridge.cortex_available", return_value=False):
        assert cortex_bridge.cortex_state() == "unavailable"
        assert cortex_bridge.tribe_running() is False
        assert cortex_bridge.cortex_vram_report() == {"available": False, "state": "unavailable"}
        assert cortex_bridge.register_cortex_tools() == 0


def test_tribe_running_only_true_for_tribe_active_state():
    for state in ["idle", "gemma_active", "swapping", "unavailable"]:
        with patch("mercury.cortex_bridge.cortex_state", return_value=state):
            assert cortex_bridge.tribe_running() is False
    with patch("mercury.cortex_bridge.cortex_state", return_value="tribe_active"):
        assert cortex_bridge.tribe_running() is True


@pytest.mark.skipif(not cortex_installed, reason="Cortex not installed in this venv")
def test_cortex_bridge_sees_real_cortex():
    assert cortex_bridge.cortex_available() is True
    state = cortex_bridge.cortex_state()
    assert state in {"idle", "gemma_active", "tribe_active", "swapping"}
    report = cortex_bridge.cortex_vram_report()
    assert report["available"] is True
    assert "total_gb" in report
    assert report["total_gb"] > 0


@pytest.mark.skipif(not cortex_installed, reason="Cortex not installed in this venv")
def test_register_cortex_tools_registers_four():
    n = cortex_bridge.register_cortex_tools()
    assert n == 4
    from tools.registry import registry
    cortex_tools = {
        e.name for e in registry._snapshot_entries() if e.toolset == cortex_bridge.CORTEX_TOOLSET
    }
    assert cortex_tools == {"brain_scan", "narrate", "visualize", "describe_input"}
