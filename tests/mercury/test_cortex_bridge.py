from unittest.mock import patch

from mercury import cortex_bridge


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
