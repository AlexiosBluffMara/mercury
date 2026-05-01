"""Reasoning-mode toggle and Ollama options builder.

Two surfaces share this logic:

* CLI:    ``mercury chat --think``
* Discord: ``/think <question>`` (registered via COMMAND_REGISTRY)
* Web:    ``?think=1`` query param on the chat surface
* Gateway: ``ReasoningMode`` is honored when constructing Ollama options

When reasoning mode is on, Mercury asks Gemma 4 to use thinking and
expands ``num_ctx`` to 16384. If GpuCoordinator says the 26B MoE fits,
the picker prefers it over E4B for higher-quality reasoning; otherwise
E4B is the fallback.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

from agent.gpu_coordinator import GpuVerdict


class ReasoningMode(str, enum.Enum):
    IMMEDIATE = "immediate"
    THINKING = "thinking"


@dataclass
class ModalityHints:
    has_image: bool = False
    has_audio: bool = False

    @property
    def is_multimodal(self) -> bool:
        return self.has_image or self.has_audio


# Models that support each modality.
TEXT_VISION_MODELS = {"gemma4:e4b", "gemma4-26b-moe", "gemma4:27b", "gemma4:31b"}
TEXT_VISION_AUDIO_MODELS = {"gemma4-26b-moe"}


def pick_model(
    verdict: GpuVerdict,
    mode: ReasoningMode,
    modality: ModalityHints | None = None,
) -> str | None:
    """Choose the best Gemma model for this turn.

    Priority:
      1. If audio is required, force the 26B MoE (only model that supports it).
      2. If thinking mode AND the 26B MoE fits, pick it.
      3. Otherwise use the verdict's recommendation.
    """
    if not verdict.can_run:
        return None

    modality = modality or ModalityHints()
    rec = verdict.recommended_model

    if modality.has_audio:
        # Audio is 26B-only. If the verdict's recommendation is bigger or
        # equal we trust it, else the caller has to wait for VRAM.
        if rec == "gemma4-26b-moe" or rec in {"gemma4:27b", "gemma4:31b"}:
            return "gemma4-26b-moe"
        return None  # audio doesn't fit; caller must queue

    if mode == ReasoningMode.THINKING:
        # Prefer the 26B MoE for reasoning when there's headroom. The
        # coordinator only recommends the 26B when it fits, so any rec
        # at-or-above E4B can be upgraded if the budget supports it.
        if rec in {"gemma4-26b-moe", "gemma4:27b", "gemma4:31b"}:
            return "gemma4-26b-moe"
        # Coordinator picked something smaller (probably tribe_active);
        # honor that — reasoning still helps even on the small model.
        return rec

    return rec


def build_ollama_options(
    mode: ReasoningMode,
    base: dict | None = None,
) -> dict:
    """Return an ``options`` dict for Ollama's /api/generate or /api/chat.

    Only the keys we care about are touched; ``base`` is preserved.
    """
    opts: dict = dict(base or {})
    if mode == ReasoningMode.THINKING:
        opts["think"] = True
        opts.setdefault("num_ctx", 16384)
    else:
        # Don't override think if caller set it explicitly via base.
        opts.setdefault("think", False)
    return opts


def parse_query_param(value: str | None) -> ReasoningMode:
    """Map ``?think=1`` / ``?think=true`` / ``?think=yes`` to thinking mode."""
    if value is None:
        return ReasoningMode.IMMEDIATE
    truthy = {"1", "true", "yes", "on", "thinking"}
    if str(value).strip().lower() in truthy:
        return ReasoningMode.THINKING
    return ReasoningMode.IMMEDIATE


def detect_modality(
    text: str | None,
    image_paths: list[str] | None = None,
    audio_paths: list[str] | None = None,
    forced: str | None = None,
) -> ModalityHints:
    """Detect modality from inputs.

    A pasted ``data:image/...;base64,`` URL counts as an image.
    ``forced`` is one of: ``scan-image``, ``describe-audio``, or None.
    """
    has_image = bool(image_paths)
    has_audio = bool(audio_paths)
    if text and "data:image/" in text and ";base64," in text:
        has_image = True
    if forced == "scan-image":
        has_image = True
    elif forced == "describe-audio":
        has_audio = True
    return ModalityHints(has_image=has_image, has_audio=has_audio)
