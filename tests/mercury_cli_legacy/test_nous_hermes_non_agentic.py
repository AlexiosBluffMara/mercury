"""Tests for the Nous-Mercury-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"mercury"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``mercury-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "mercury" tag namespace.

``is_nous_mercury_non_agentic`` should only match the actual Nous Research
Mercury-3 / Mercury-4 chat family.
"""

from __future__ import annotations

import pytest

from mercury_cli.model_switch import (
    _MERCURY_MODEL_WARNING,
    _check_mercury_model_warning,
    is_nous_mercury_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Mercury-3-Llama-3.1-70B",
        "NousResearch/Mercury-3-Llama-3.1-405B",
        "mercury-3",
        "Mercury-3",
        "mercury-4",
        "mercury-4-405b",
        "mercury_4_70b",
        "openrouter/mercury3:70b",
        "openrouter/nousresearch/mercury-4-405b",
        "NousResearch/Mercury3",
        "mercury-3.1",
    ],
)
def test_matches_real_nous_mercury_chat_models(model_name: str) -> None:
    assert is_nous_mercury_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Mercury 3/4"
    )
    assert _check_mercury_model_warning(model_name) == _MERCURY_MODEL_WARNING


@pytest.mark.parametrize(
    "model_name",
    [
        # Kyle's local Modelfile — qwen3:14b under a custom tag
        "mercury-brain:qwen3-14b-ctx16k",
        "mercury-brain:qwen3-14b-ctx32k",
        "mercury-honcho:qwen3-8b-ctx8k",
        # Plain unrelated models
        "qwen3:14b",
        "qwen3-coder:30b",
        "qwen2.5:14b",
        "claude-opus-4-6",
        "anthropic/claude-sonnet-4.5",
        "gpt-5",
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "deepseek-chat",
        # Non-chat Mercury models we don't warn about
        "mercury-llm-2",
        "mercury2-pro",
        "nous-mercury-2-mistral",
        # Edge cases
        "",
        "mercury",  # bare "mercury" isn't the 3/4 family
        "mercury-brain",
        "brain-mercury-3-impostor",  # "3" not preceded by /: boundary
    ],
)
def test_does_not_match_unrelated_models(model_name: str) -> None:
    assert not is_nous_mercury_non_agentic(model_name), (
        f"expected {model_name!r} NOT to be flagged as Nous Mercury 3/4"
    )
    assert _check_mercury_model_warning(model_name) == ""


def test_none_like_inputs_are_safe() -> None:
    assert is_nous_mercury_non_agentic("") is False
    # Defensive: the helper shouldn't crash on None-ish falsy input either.
    assert _check_mercury_model_warning("") == ""
