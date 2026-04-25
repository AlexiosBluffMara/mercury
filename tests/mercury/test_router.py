from unittest.mock import patch

from mercury import copilot_models as cm
from mercury import router
from mercury.router import BrainPreference, Intent


def test_classify_code_keywords():
    assert router.classify_turn("fix the bug in auth.py") == Intent.CODE
    assert router.classify_turn("write a function that ...") == Intent.CODE
    assert router.classify_turn("debug this stack trace: ...") == Intent.CODE


def test_classify_cortex_keywords():
    assert router.classify_turn("run a brain scan on the clip") == Intent.CORTEX
    assert router.classify_turn("narrate the cortical activations") == Intent.CORTEX
    assert router.classify_turn("BOLD response for tribe v2") == Intent.CORTEX


def test_classify_vision_keywords():
    assert router.classify_turn("describe this image of a cat") == Intent.VISION
    assert router.classify_turn("what's in the screenshot") == Intent.VISION


def test_classify_quick_for_short_messages():
    assert router.classify_turn("hi") == Intent.QUICK
    assert router.classify_turn("set timer 10m") == Intent.QUICK
    assert router.classify_turn("what time is it") == Intent.QUICK


def test_pick_brain_routes_code_to_copilot():
    with patch("mercury.cortex_bridge.tribe_running", return_value=False):
        choice = router.pick_brain("write a function to sort tuples")
    assert choice == cm.DEFAULT_FULLTIME_BRAIN


def test_pick_brain_cortex_pure_uses_gemma():
    with patch("mercury.cortex_bridge.tribe_running", return_value=False):
        choice = router.pick_brain("brain_scan this video", cortex_pure=True)
    assert choice == cm.GEMMA_E4B


def test_pick_brain_cortex_falls_back_to_copilot_when_tribe_running():
    with patch("mercury.cortex_bridge.tribe_running", return_value=True):
        choice = router.pick_brain("brain_scan this video", cortex_pure=True)
    assert choice == cm.DEFAULT_FULLTIME_BRAIN


def test_pick_brain_vision_falls_back_to_gpt4o_when_gemma_blocked():
    with patch("mercury.cortex_bridge.tribe_running", return_value=True):
        choice = router.pick_brain("describe this image")
    assert choice == cm.DEFAULT_VISION_BRAIN
    assert choice.supports_vision


def test_pick_brain_explicit_preference_wins():
    with patch("mercury.cortex_bridge.tribe_running", return_value=False):
        choice = router.pick_brain("hello", preference=BrainPreference.COPILOT)
    assert choice == cm.DEFAULT_FULLTIME_BRAIN

    with patch("mercury.cortex_bridge.tribe_running", return_value=False):
        choice = router.pick_brain("write code", preference=BrainPreference.GEMMA)
    assert choice == cm.GEMMA_E4B


def test_pick_brain_escalate_returns_paid_tier():
    choice = router.pick_brain("anything", preference=BrainPreference.ESCALATE)
    assert choice.multiplier >= 1.0
