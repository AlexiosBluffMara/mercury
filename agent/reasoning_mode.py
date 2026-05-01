"""Reasoning-mode toggle, Ollama options builder, two-pass progressive answer.

Mercury exposes **two answer modes** to every surface (CLI, Discord, web):

* **`short`** (default) — fast, single-pass answer. Gemma's thinking is OFF.
  One Ollama call, streamed back to the user.
* **`long`** — *progressive enhancement*. Mercury first delivers the same
  fast answer (think=false), and **only after that completes** does it
  re-run the prompt with thinking ON (think=true, num_ctx=16384) and
  edit/replace the original answer with the deeper response.

The two-pass design exists because thinking-mode answers can take 30–90 s
on the local 5090 — too slow for a chat UX. The user sees something
immediately, then the better answer streams in to replace it.

Surfaces
--------
* CLI:    ``mercury chat --long`` / ``--short`` (also ``-l`` / ``-s``)
* Discord: ``/long <question>``, ``/short <question>``
* Web:    ``?long=1`` / ``?short=1`` query param on the chat surface
* Gateway: ``ReasoningMode`` is honored at the Ollama call site

Backwards compatibility
-----------------------
The legacy ``IMMEDIATE`` / ``THINKING`` enum values remain as deprecated
aliases of ``SHORT`` / ``LONG`` so existing imports keep working. The
deprecated ``--think`` flag still maps to ``--long``. New code should use
``ReasoningMode.SHORT`` and ``ReasoningMode.LONG``.
"""
from __future__ import annotations

import asyncio
import enum
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from agent.gpu_coordinator import GpuVerdict


class ReasoningMode(str, enum.Enum):
    SHORT = "short"           # canonical: fast, think=false, one pass
    LONG = "long"             # canonical: progressive — fast first, then deep replaces it
    # Deprecated aliases (kept so legacy callers keep working).
    IMMEDIATE = "short"
    THINKING = "long"


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
      2. If LONG mode AND the 26B MoE fits, pick it for the deep pass.
      3. Otherwise use the verdict's recommendation (fast pass / SHORT default).
    """
    if not verdict.can_run:
        return None

    modality = modality or ModalityHints()
    rec = verdict.recommended_model

    if modality.has_audio:
        if rec == "gemma4-26b-moe" or rec in {"gemma4:27b", "gemma4:31b"}:
            return "gemma4-26b-moe"
        return None  # audio doesn't fit; caller must queue

    if mode == ReasoningMode.LONG:
        # Deep pass prefers the 26B MoE when there's headroom. Coordinator
        # only recommends the 26B when it fits, so any rec at-or-above E4B
        # can be upgraded.
        if rec in {"gemma4-26b-moe", "gemma4:27b", "gemma4:31b"}:
            return "gemma4-26b-moe"
        # Coordinator picked something smaller (probably tribe_active);
        # honor that — the deep pass still runs with think=true even on
        # the smaller model.
        return rec

    return rec


def build_ollama_options(
    mode: ReasoningMode,
    base: dict | None = None,
) -> dict:
    """Return an ``options`` dict for Ollama's /api/generate or /api/chat.

    SHORT mode → ``think=false`` (default, fast).
    LONG mode  → ``think=true``, ``num_ctx=16384`` (the deep pass).

    For the **two-pass** flow, callers run this twice: first with SHORT (the
    fast pass that delivers immediately), then with LONG (the deep pass that
    replaces the original answer).
    """
    opts: dict = dict(base or {})
    if mode == ReasoningMode.LONG:
        opts["think"] = True
        opts.setdefault("num_ctx", 16384)
    else:
        # SHORT (default). Don't override think if caller set it explicitly.
        opts.setdefault("think", False)
    return opts


def parse_query_param(value: str | None, *, key: str | None = None) -> ReasoningMode:
    """Map a query-param value to a ReasoningMode.

    Accepts:
      * ``?long=1`` / ``?long=true`` / ``?long=yes`` → LONG
      * ``?short=1`` / ``?short=true`` → SHORT (explicit, useful for clearing)
      * Legacy ``?think=1`` → LONG (kept for back-compat)

    The ``key`` arg lets callers be explicit about which param they parsed
    (``?long`` vs ``?short``); when omitted the function infers from the
    truthiness of the value alone.
    """
    if value is None:
        return ReasoningMode.SHORT
    truthy = {"1", "true", "yes", "on", "long", "thinking"}
    val = str(value).strip().lower()
    if val in truthy:
        # ``?short=1`` should give SHORT; ``?long=1`` should give LONG.
        if key and key.lower() == "short":
            return ReasoningMode.SHORT
        return ReasoningMode.LONG
    return ReasoningMode.SHORT


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


# ─────────────────────────────────────────────────────────────────────────────
# Two-pass progressive answer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TwoPassEvent:
    """One unit of progress in a two-pass answer.

    Surfaces dispatch on ``kind``:
      * ``short_chunk``  — token from the fast pass, append to the visible answer
      * ``short_done``   — fast pass complete; final ``text`` is the full short answer
      * ``long_starting`` — about to begin the deep pass (UI may show a "thinking"
        indicator over the existing short answer)
      * ``long_chunk``   — token from the deep pass; the surface should be
        *replacing* the short answer with the accumulating long answer
      * ``long_done``    — deep pass complete; final ``text`` is the full long answer
      * ``error``        — pass failed; ``text`` is the error message; surface
        should keep whatever was last delivered
    """
    kind: str
    text: str = ""
    pass_id: str = ""              # "short" | "long"
    model: str | None = None       # model that produced this token


GenerateFn = Callable[[str, dict], AsyncIterator[str]]
"""Signature: ``async def generate(model: str, opts: dict) -> AsyncIterator[str]``.

Yields token chunks as they arrive from Ollama. Surfaces inject their own
generator (the gateway has one; the CLI has one; the web layer has one)
so this module stays free of HTTP transport details.
"""


async def run_two_pass(
    *,
    prompt: str,
    mode: ReasoningMode,
    verdict: GpuVerdict,
    generate: GenerateFn,
    modality: ModalityHints | None = None,
    on_event: Callable[[TwoPassEvent], Awaitable[None]] | None = None,
) -> str:
    """Run the progressive two-pass answer.

    Always emits a SHORT pass first. If ``mode == LONG``, follows with a
    second pass using thinking enabled — the surface is expected to *replace*
    the short answer with the long one as tokens arrive.

    Returns the final answer text (long if LONG and it succeeded; otherwise short).

    Surfaces consume events via ``on_event``:

    .. code-block:: python

        async def on_event(ev: TwoPassEvent) -> None:
            if ev.kind == "short_chunk":
                await ws.send(ev.text)            # append
            elif ev.kind == "long_starting":
                await ws.send_message_edit(...)   # show thinking indicator
            elif ev.kind == "long_chunk":
                await ws.send_replace(ev.text)    # replace in place

    The function never raises for a single-pass failure — it emits an
    ``error`` event and continues if any partial text was produced.
    """
    async def _emit(ev: TwoPassEvent) -> None:
        if on_event:
            await on_event(ev)

    # Short pass (always). think=false.
    short_model = pick_model(verdict, ReasoningMode.SHORT, modality)
    if short_model is None:
        await _emit(TwoPassEvent(kind="error", text=verdict.reason or "no model fits"))
        return ""

    short_opts = build_ollama_options(ReasoningMode.SHORT)
    short_acc: list[str] = []
    try:
        async for chunk in generate(short_model, {"prompt": prompt, "options": short_opts}):
            short_acc.append(chunk)
            await _emit(TwoPassEvent(kind="short_chunk", text=chunk,
                                     pass_id="short", model=short_model))
    except Exception as exc:  # noqa: BLE001 — surface decides recovery
        await _emit(TwoPassEvent(kind="error", text=f"short pass failed: {exc}",
                                 pass_id="short"))
        return "".join(short_acc)

    short_text = "".join(short_acc)
    await _emit(TwoPassEvent(kind="short_done", text=short_text,
                             pass_id="short", model=short_model))

    if mode != ReasoningMode.LONG:
        return short_text

    # Long pass — only if user asked for it. think=true, may upgrade to 26B MoE.
    long_model = pick_model(verdict, ReasoningMode.LONG, modality)
    if long_model is None:
        await _emit(TwoPassEvent(kind="error",
                                 text="long pass needs more VRAM than is available right now",
                                 pass_id="long"))
        return short_text

    await _emit(TwoPassEvent(kind="long_starting", text=short_text,
                             pass_id="long", model=long_model))

    long_opts = build_ollama_options(ReasoningMode.LONG)
    # Tell the deep model what the fast model just said so it can refine
    # rather than restart from scratch.
    enhanced_prompt = (
        f"{prompt}\n\n"
        f"<previous_answer>\n{short_text}\n</previous_answer>\n\n"
        "Refine, correct, or expand the previous answer. Be more thorough; "
        "engage the user's question more deeply. Output only the improved "
        "answer — the previous one will be replaced wholesale."
    )

    long_acc: list[str] = []
    try:
        async for chunk in generate(long_model, {"prompt": enhanced_prompt, "options": long_opts}):
            long_acc.append(chunk)
            await _emit(TwoPassEvent(kind="long_chunk", text=chunk,
                                     pass_id="long", model=long_model))
    except Exception as exc:  # noqa: BLE001
        await _emit(TwoPassEvent(kind="error", text=f"long pass failed: {exc}",
                                 pass_id="long"))
        # Long pass failed mid-stream. Keep what we have; if empty, fall back to short.
        return "".join(long_acc) or short_text

    long_text = "".join(long_acc)
    await _emit(TwoPassEvent(kind="long_done", text=long_text,
                             pass_id="long", model=long_model))
    return long_text


# ─────────────────────────────────────────────────────────────────────────────
# Sync wrapper for CLI / non-async callers
# ─────────────────────────────────────────────────────────────────────────────

def run_two_pass_sync(
    *,
    prompt: str,
    mode: ReasoningMode,
    verdict: GpuVerdict,
    generate: GenerateFn,
    modality: ModalityHints | None = None,
    on_event: Callable[[TwoPassEvent], Awaitable[None]] | None = None,
) -> str:
    """Sync wrapper around :func:`run_two_pass` for CLI scripts.

    Spins up an asyncio loop. Don't call from inside an existing event loop.
    """
    return asyncio.run(
        run_two_pass(
            prompt=prompt,
            mode=mode,
            verdict=verdict,
            generate=generate,
            modality=modality,
            on_event=on_event,
        )
    )
