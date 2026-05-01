"""Unit tests for reasoning mode + multimodal model selection."""
from __future__ import annotations

from agent.gpu_coordinator import GpuVerdict
from agent.reasoning_mode import (
    ModalityHints,
    ReasoningMode,
    build_ollama_options,
    detect_modality,
    parse_query_param,
    pick_model,
)


# --- options ----------------------------------------------------------


def test_thinking_mode_sets_think_and_ctx():
    opts = build_ollama_options(ReasoningMode.THINKING)
    assert opts["think"] is True
    assert opts["num_ctx"] == 16384


def test_immediate_mode_defaults_think_false():
    opts = build_ollama_options(ReasoningMode.IMMEDIATE)
    assert opts["think"] is False
    assert "num_ctx" not in opts


def test_existing_options_preserved():
    opts = build_ollama_options(ReasoningMode.THINKING, base={"temperature": 0.4, "num_ctx": 8192})
    assert opts["temperature"] == 0.4
    # Caller-provided num_ctx wins via setdefault
    assert opts["num_ctx"] == 8192
    assert opts["think"] is True


# --- query param parsing ---------------------------------------------


def test_query_param_truthy_values():
    for v in ("1", "true", "yes", "on", "thinking", "TRUE", " yes "):
        assert parse_query_param(v) == ReasoningMode.THINKING


def test_query_param_falsy_values():
    for v in (None, "0", "false", "no", "off", ""):
        assert parse_query_param(v) == ReasoningMode.IMMEDIATE


# --- modality detection ----------------------------------------------


def test_detect_image_from_attachment():
    m = detect_modality("hi", image_paths=["/tmp/foo.png"])
    assert m.has_image
    assert not m.has_audio
    assert m.is_multimodal


def test_detect_image_from_base64_in_text():
    m = detect_modality("look: data:image/png;base64,iVBORw0K...", image_paths=None)
    assert m.has_image


def test_detect_audio_from_attachment():
    m = detect_modality(None, audio_paths=["/tmp/clip.wav"])
    assert m.has_audio


def test_forced_scan_image():
    m = detect_modality("plain text", forced="scan-image")
    assert m.has_image


def test_forced_describe_audio():
    m = detect_modality("plain text", forced="describe-audio")
    assert m.has_audio


def test_text_only_inputs():
    m = detect_modality("just words")
    assert not m.is_multimodal


# --- model picker ----------------------------------------------------


def _verdict(model: str | None, can_run: bool = True) -> GpuVerdict:
    return GpuVerdict(can_run=can_run, recommended_model=model, reason="t")


def test_picker_returns_none_when_blocked():
    v = GpuVerdict(can_run=False, recommended_model=None, reason="x", wait_seconds=10)
    assert pick_model(v, ReasoningMode.IMMEDIATE) is None


def test_picker_immediate_uses_recommendation():
    assert pick_model(_verdict("gemma4:e4b"), ReasoningMode.IMMEDIATE) == "gemma4:e4b"
    assert pick_model(_verdict("gemma4:4b"), ReasoningMode.IMMEDIATE) == "gemma4:4b"


def test_picker_thinking_upgrades_to_26b_when_room():
    # Coordinator says we have room for a 27B-class model; thinking mode picks 26B MoE
    assert pick_model(_verdict("gemma4:31b"), ReasoningMode.THINKING) == "gemma4-26b-moe"
    assert pick_model(_verdict("gemma4-26b-moe"), ReasoningMode.THINKING) == "gemma4-26b-moe"


def test_picker_thinking_with_e4b_stays_on_e4b():
    # Coordinator only gave us E4B (e.g. tribe_active) — don't try to upgrade
    assert pick_model(_verdict("gemma4:e4b"), ReasoningMode.THINKING) == "gemma4:e4b"


def test_picker_thinking_with_4b_stays_on_4b():
    assert pick_model(_verdict("gemma4:4b"), ReasoningMode.THINKING) == "gemma4:4b"


def test_picker_audio_forces_26b_moe():
    audio = ModalityHints(has_audio=True)
    assert pick_model(_verdict("gemma4:31b"), ReasoningMode.IMMEDIATE, audio) == "gemma4-26b-moe"


def test_picker_audio_when_no_room_returns_none():
    audio = ModalityHints(has_audio=True)
    # Tribe loaded -> only 4B was recommended -> no audio path possible
    assert pick_model(_verdict("gemma4:4b"), ReasoningMode.IMMEDIATE, audio) is None


def test_picker_image_uses_recommendation():
    img = ModalityHints(has_image=True)
    # Image works on E4B and up; recommendation honored
    assert pick_model(_verdict("gemma4:e4b"), ReasoningMode.IMMEDIATE, img) == "gemma4:e4b"
