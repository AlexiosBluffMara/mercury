"""Copilot model catalog and selection helpers for Mercury.

Multipliers come from the GitHub Copilot premium-request table
(docs.github.com/en/copilot/concepts/billing/copilot-requests).  On
Pro+ the only models with multiplier 0 are GPT-5 mini, GPT-4o, GPT-4.1,
and Raptor mini.  Mercury's "fulltime brain" rotates between those
three.  The 1x escalation tier (Sonnet 4.6, GPT-5.4, Gemini 2.5 Pro,
GPT-5.2/5.3-Codex) is opt-in via /brain commands or config.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    provider: str               # "copilot" | "ollama" | "vertex" | "ai-studio"
    multiplier: float           # premium-request cost; 0 = unlimited on Pro+
    api_mode: str               # "chat_completions" | "codex_responses" | "anthropic_messages"
    supports_vision: bool
    supports_tools: bool
    note: str = ""


GPT5_MINI = ModelDescriptor(
    model_id="gpt-5-mini",
    provider="copilot",
    multiplier=0.0,
    api_mode="chat_completions",
    supports_vision=False,
    supports_tools=True,
    note="Mercury default fulltime brain — newest 0x model, GPT-5 family reasoning.",
)

GPT4O = ModelDescriptor(
    model_id="gpt-4o",
    provider="copilot",
    multiplier=0.0,
    api_mode="chat_completions",
    supports_vision=True,
    supports_tools=True,
    note="0x multimodal — used for vision when Gemma 4 isn't available.",
)

GPT41 = ModelDescriptor(
    model_id="gpt-4.1",
    provider="copilot",
    multiplier=0.0,
    api_mode="chat_completions",
    supports_vision=False,
    supports_tools=True,
    note="0x backup; consistency mode when GPT-5 mini misbehaves.",
)

GEMMA_E4B = ModelDescriptor(
    model_id="gemma4:e4b",
    provider="ollama",
    multiplier=0.0,
    api_mode="chat_completions",
    supports_vision=True,
    supports_tools=False,
    note="Local Gemma 4 E4B (~10 GB VRAM, ~196 tok/s on RTX 5090).",
)


SONNET_46 = ModelDescriptor(
    model_id="claude-sonnet-4-6",
    provider="copilot",
    multiplier=1.0,
    api_mode="anthropic_messages",
    supports_vision=True,
    supports_tools=True,
    note="1x escalation; best for hard reasoning + long agentic chains.",
)

GPT54 = ModelDescriptor(
    model_id="gpt-5.4",
    provider="copilot",
    multiplier=1.0,
    api_mode="chat_completions",
    supports_vision=False,
    supports_tools=True,
    note="1x escalation; OpenAI flagship code+reasoning model.",
)

GPT53_CODEX = ModelDescriptor(
    model_id="gpt-5.3-codex",
    provider="copilot",
    multiplier=1.0,
    api_mode="codex_responses",
    supports_vision=False,
    supports_tools=True,
    note="1x escalation; LTS code-tuned model through Feb 2027.",
)

GEMINI_25_PRO = ModelDescriptor(
    model_id="gemini-2.5-pro",
    provider="vertex",
    multiplier=1.0,
    api_mode="chat_completions",
    supports_vision=True,
    supports_tools=True,
    note="Long-context / multimodal escalation via Gemini Enterprise Agent Platform.",
)


ZERO_PREMIUM_MODELS: tuple[ModelDescriptor, ...] = (GPT5_MINI, GPT4O, GPT41)
ESCALATION_MODELS: tuple[ModelDescriptor, ...] = (SONNET_46, GPT54, GPT53_CODEX, GEMINI_25_PRO)
LOCAL_MODELS: tuple[ModelDescriptor, ...] = (GEMMA_E4B,)
ALL_MODELS: tuple[ModelDescriptor, ...] = ZERO_PREMIUM_MODELS + ESCALATION_MODELS + LOCAL_MODELS

DEFAULT_FULLTIME_BRAIN = GPT5_MINI
DEFAULT_VISION_BRAIN = GPT4O
DEFAULT_PARTTIME_BRAIN = GEMMA_E4B
DEFAULT_CODE_ESCALATION = GPT53_CODEX
DEFAULT_REASONING_ESCALATION = SONNET_46


def by_id(model_id: str) -> ModelDescriptor | None:
    for m in ALL_MODELS:
        if m.model_id == model_id:
            return m
    return None


def is_zero_premium(model_id: str) -> bool:
    m = by_id(model_id)
    return bool(m and m.multiplier == 0.0 and m.provider == "copilot")


def best_zero_premium_for(*, vision: bool = False) -> ModelDescriptor:
    if vision:
        return DEFAULT_VISION_BRAIN
    return DEFAULT_FULLTIME_BRAIN
