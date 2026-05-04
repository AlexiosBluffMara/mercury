"""Dual-mode response plugin for Mercury.

Pipeline (single-model VRAM mode — default for 32 GB cards):
  1. User sends message.
  2. `respond_fast` → gemma4:e4b, thinking off → reply within ~1 s.
  3. If the trigger matches, `respond_deep` is scheduled on the gateway's
     event loop. Ollama evicts E4B and loads 26B (one-time cost: ~4-8 s
     load + the deep generation itself). When the deep call returns, the
     gateway edits (or follows up on) the original bot message.
  4. Optionally: after the deep reply lands, the next user turn triggers
     a swap back to E4B for fast latency. Ollama handles this automatically
     based on the `model` field in each request.

VRAM math: E4B = 10 GB, 26B = 19 GB. Sum (29 GB) fits a 32 GB card on
paper, but KV cache + activations + display reserved push you over the
edge. We chose one-at-a-time as the safe default; if you ever switch to
a 48+ GB card, set `max_loaded_models: 2` in `config.yaml` and the swap
disappears.

The plugin doesn't talk to Discord/WhatsApp directly — it returns
intermediate `Response` objects with the platform-aware `edit_strategy`
so the gateway's per-platform adapter can apply the right verb.

Wire-up note: Mercury's plugin loader expects `entrypoint = dual_mode:run`
or similar; if you're on a Mercury Agent build that doesn't have a hook for
`on_user_message` yet, this plugin still imports cleanly — it just sits
idle until you wire `respond` into your gateway dispatcher.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml

# --------------------------------------------------------------------------
# Config (loaded from plugin.yaml, but defaults are baked here so the plugin
# is functional even without a config layer).
# --------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent / "plugin.yaml"
_DEFAULTS = {
    "fast": {
        "model":    "gemma4:e4b",
        "provider": "custom:ollama-local",
        "thinking": False,
        "temperature": 0.6,
        "max_tokens": 600,
        "timeout_s": 12,
    },
    "deep": {
        "model":    "gemma4:26b",
        "provider": "custom:ollama-local",
        "thinking": True,
        "temperature": 0.4,
        "max_tokens": 2000,
        "timeout_s": 90,
        "deep_trigger_chars": 280,
        "deep_trigger_phrases": ["/deep", "/think", "?expand", "explain in detail"],
        "edit_strategy": {
            "discord":  "replace_in_place",
            "whatsapp": "follow_up",
            "telegram": "replace_in_place",
            "slack":    "replace_in_place",
            "cli":      "append_below",
        },
    },
}


def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return _DEFAULTS
    try:
        cfg = yaml.safe_load(_CONFIG_PATH.read_text("utf-8")) or {}
    except yaml.YAMLError:
        return _DEFAULTS
    merged = json.loads(json.dumps(_DEFAULTS))   # deep copy
    for k, v in (cfg.get("config") or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


CONFIG = _load_config()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


# --------------------------------------------------------------------------
# Trigger logic
# --------------------------------------------------------------------------

def should_run_deep(user_text: str, fast_used_tool: bool = False) -> bool:
    deep = CONFIG["deep"]
    if fast_used_tool:
        return True
    if len(user_text) > deep["deep_trigger_chars"]:
        return True
    lower = user_text.lower()
    return any(p.lower() in lower for p in deep["deep_trigger_phrases"])


# --------------------------------------------------------------------------
# Ollama call (OpenAI-style chat completion via Ollama's /v1)
# --------------------------------------------------------------------------

def _ollama_chat(
    model: str,
    system: str,
    user: str,
    *,
    thinking: bool,
    temperature: float,
    max_tokens: int,
    timeout_s: int,
) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Ollama-specific extra: think=false suppresses chain-of-thought tokens
        # from being emitted; supported on Gemma 4 / Qwen3 / DeepSeek-R1 models.
        "extra_body": {"think": thinking},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - started
    msg = payload.get("choices", [{}])[0].get("message", {})
    return {
        "text": (msg.get("content") or "").strip(),
        "usage": payload.get("usage", {}),
        "elapsed_s": round(elapsed, 2),
        "model": model,
    }


async def _ollama_chat_async(*args, **kwargs) -> dict:
    return await asyncio.get_event_loop().run_in_executor(
        None, lambda: _ollama_chat(*args, **kwargs)
    )


# --------------------------------------------------------------------------
# Public API used by the gateway dispatcher
# --------------------------------------------------------------------------

@dataclass
class Response:
    text: str
    model: str
    elapsed_s: float
    is_fast: bool
    edit_strategy: str = "replace_in_place"
    usage: dict = field(default_factory=dict)


@dataclass
class DualModeContext:
    user_text:     str
    system_prompt: str = "You are Mercury, the user's local-first agent on a 5090. Be useful, concise, and accurate. If you're not sure, say so."
    platform:      str = "discord"      # one of: discord, whatsapp, telegram, slack, cli
    history:       list[dict] = field(default_factory=list)


async def respond_fast(ctx: DualModeContext) -> Response:
    cfg = CONFIG["fast"]
    out = await _ollama_chat_async(
        cfg["model"],
        ctx.system_prompt,
        ctx.user_text,
        thinking=cfg["thinking"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
        timeout_s=cfg["timeout_s"],
    )
    edit = CONFIG["deep"]["edit_strategy"].get(ctx.platform, "replace_in_place")
    return Response(
        text=out["text"], model=out["model"], elapsed_s=out["elapsed_s"],
        is_fast=True, edit_strategy=edit, usage=out["usage"],
    )


async def respond_deep(ctx: DualModeContext, fast_text: str) -> Response:
    cfg = CONFIG["deep"]
    deep_system = (
        ctx.system_prompt
        + "\n\nA fast reply has already been sent to the user (below). Improve it: "
        "fix factual or logical errors, add depth where the fast reply hand-waved, "
        "tighten the prose. Output only the improved reply text — no preamble, no "
        "bullet about what you changed.\n\n"
        f"FAST_REPLY:\n{fast_text}"
    )
    out = await _ollama_chat_async(
        cfg["model"],
        deep_system,
        ctx.user_text,
        thinking=cfg["thinking"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
        timeout_s=cfg["timeout_s"],
    )
    edit = cfg["edit_strategy"].get(ctx.platform, "replace_in_place")
    return Response(
        text=out["text"], model=out["model"], elapsed_s=out["elapsed_s"],
        is_fast=False, edit_strategy=edit, usage=out["usage"],
    )


async def respond(
    ctx: DualModeContext,
    *,
    on_fast:  Callable[[Response], Awaitable[None]] | None = None,
    on_deep:  Callable[[Response], Awaitable[None]] | None = None,
    fast_used_tool: bool = False,
) -> tuple[Response, Response | None]:
    """Run the fast pass, optionally schedule the deep pass.

    Caller passes two async callbacks: `on_fast` to send the immediate reply,
    `on_deep` to edit/follow-up when the deep pass finishes. The function
    returns once the deep pass is settled (or skipped).
    """
    fast = await respond_fast(ctx)
    if on_fast is not None:
        await on_fast(fast)

    if not should_run_deep(ctx.user_text, fast_used_tool=fast_used_tool):
        return fast, None

    deep = await respond_deep(ctx, fast.text)
    if on_deep is not None:
        await on_deep(deep)
    return fast, deep


# --------------------------------------------------------------------------
# CLI smoke-test:  python -m plugins.dual_mode.dual_mode "your prompt here"
# --------------------------------------------------------------------------

def _cli_smoke(prompt: str) -> int:
    async def _run():
        async def _print_fast(r: Response):
            print(f"\n[FAST  {r.model}  {r.elapsed_s}s]")
            print(r.text)
            print("─── deep pass running ───")

        async def _print_deep(r: Response):
            print(f"\n[DEEP  {r.model}  {r.elapsed_s}s]")
            print(r.text)

        ctx = DualModeContext(user_text=prompt, platform="cli")
        fast, deep = await respond(ctx, on_fast=_print_fast, on_deep=_print_deep)
        if deep is None:
            print("\n(no deep pass — under threshold)")
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli_smoke(" ".join(sys.argv[1:]) or "Explain V1 in two sentences."))
