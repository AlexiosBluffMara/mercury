"""Bridge from Mercury into the Cortex package at D:\\cortex.

Mercury and Cortex run in the same Python venv when they're co-located.
This module provides:

  - cortex_available() / cortex_state() / cortex_vram_report() — read-side
    helpers used by the dual-brain router to honor Cortex's GPU lock.
  - registry.register() calls for the four Cortex tools (brain_scan,
    narrate, visualize, describe_input) so they appear as Mercury tools
    under the toolset "cortex".

If `cortex` isn't importable, every function degrades to a clean
"unavailable" response and no tools are registered.  Mercury still
boots; the agent simply won't surface Cortex capabilities.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

CORTEX_TOOLSET = "cortex"


def cortex_available() -> bool:
    try:
        import cortex  # noqa: F401
        return True
    except ImportError:
        return False


def cortex_state() -> str:
    """Return Cortex GPU state as a string: idle/gemma_active/tribe_active/swapping/unavailable."""
    if not cortex_available():
        return "unavailable"
    try:
        from cortex.gpu_scheduler import get_scheduler
        return get_scheduler().state.value
    except Exception as exc:
        logger.warning("cortex_state failed: %s", exc)
        return "unavailable"


def tribe_running() -> bool:
    return cortex_state() == "tribe_active"


def cortex_vram_report() -> dict:
    if not cortex_available():
        return {"available": False, "state": "unavailable"}
    try:
        from cortex.gpu_scheduler import get_scheduler
        report = get_scheduler().vram_report()
        report["available"] = True
        return report
    except Exception as exc:
        logger.warning("cortex_vram_report failed: %s", exc)
        return {"available": False, "state": "unavailable", "error": str(exc)}


def _wrap_cortex_tool(execute: Callable[..., Awaitable[dict]]) -> Callable[..., Awaitable[dict]]:
    """Wrap a Cortex tool's execute() so registry-style call args (`args`, **kw) flow through."""
    async def handler(args: dict | None = None, **_kw: Any) -> dict:
        kwargs = args or {}
        try:
            return await execute(**kwargs)
        except ImportError as exc:
            return {"ok": False, "error": "cortex_unavailable", "message": str(exc)}
        except Exception as exc:
            logger.exception("cortex tool failed")
            return {"ok": False, "error": "tool_error", "message": str(exc)}
    return handler


def _check_cortex_ready() -> bool:
    return cortex_available()


def register_cortex_tools() -> int:
    """Register the four Cortex tools.  Returns count registered, 0 if cortex missing."""
    if not cortex_available():
        logger.info("Cortex not available; skipping Cortex tool registration")
        return 0

    try:
        from cortex_hermes_tools import (  # type: ignore[import-not-found]
            brain_scan, describe_input, narrate, visualize,
        )
    except ImportError:
        try:
            from hermes.tools import brain_scan, describe_input, narrate, visualize  # noqa: F401
        except ImportError as exc:
            logger.warning("Cortex tool modules not importable: %s", exc)
            return 0

    from tools.registry import registry

    count = 0
    for tool_module, emoji in (
        (brain_scan, "🧠"),
        (narrate, "💬"),
        (visualize, "📊"),
        (describe_input, "👁"),
    ):
        try:
            registry.register(
                name=tool_module.TOOL_SCHEMA["name"],
                toolset=CORTEX_TOOLSET,
                schema=tool_module.TOOL_SCHEMA,
                handler=_wrap_cortex_tool(tool_module.execute),
                check_fn=_check_cortex_ready,
                requires_env=[],
                is_async=True,
                description=tool_module.TOOL_SCHEMA.get("description", ""),
                emoji=emoji,
            )
            count += 1
        except Exception:
            logger.exception("Failed to register cortex tool %s", tool_module.TOOL_SCHEMA.get("name"))

    logger.info("Registered %d Cortex tools", count)
    return count
