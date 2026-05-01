"""Public web routes: `/chat` (HTML), `/api/chat` (JSON), `/api/health`.

These are layered on top of the existing aiohttp app constructed by
`gateway/platforms/api_server.py`. They share the same server / port
but have their own rate-limit middleware so the operator's
OpenAI-compatible `/v1/*` endpoints stay unaffected.

Wire-up:

    from gateway.web import register_public_web_routes
    register_public_web_routes(self._app, agent_runner=self._agent_runner)

Call this in `APIServerAdapter.connect()` after the existing routes are
added. ``agent_runner`` is any awaitable that maps a prompt string to a
reply string — typically a thin wrapper around the same code path
`_handle_chat_completions` already uses.

If the api_server adapter doesn't yet expose an agent runner, this
module falls back to a polite 503 so the route still answers and the
operator can see the request in the external log.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None  # type: ignore[assignment]

from gateway.external_limits import get_external_limits
from gateway.external_logging import StopWatch, log_external_request

logger = logging.getLogger(__name__)

_CHAT_HTML = Path(__file__).parent / "chat.html"
_MAX_PROMPT_BYTES = 8000

AgentRunner = Callable[[str], Awaitable[str]]


def _client_ip(request: "web.Request") -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("X-Real-IP", "")
    if real:
        return real.strip()
    peer = request.transport.get_extra_info("peername") if request.transport else None
    if peer:
        return peer[0]
    return "0.0.0.0"


async def _handle_chat_html(request: "web.Request") -> "web.Response":
    try:
        body = _CHAT_HTML.read_bytes()
    except OSError:
        return web.Response(status=500, text="chat.html missing")
    return web.Response(
        body=body,
        content_type="text/html",
        charset="utf-8",
        headers={"Cache-Control": "public, max-age=60"},
    )


async def _handle_health_public(request: "web.Request") -> "web.Response":
    """Public-facing health: online state, daily usage, free VRAM."""
    limits = get_external_limits()
    payload: dict[str, Any] = {
        "status": "online" if limits.enabled else "paused",
        "external_enabled": limits.enabled,
        "daily_used": limits.daily_used,
        "daily_cap": limits.daily_cap,
        "model": "gemma3",
        "host": "Soumit's RTX 5090, Chicago",
        "collab": "Alexios Bluff Mara × Illinois State University",
    }
    payload["vram_free_gb"] = _vram_free_gb()
    return web.json_response(payload, headers={"Cache-Control": "no-store"})


def _vram_free_gb() -> Optional[float]:
    """Best-effort free-VRAM probe. Returns None if pynvml is unavailable."""
    try:
        import pynvml  # type: ignore[import-not-found]
        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return round(mem.free / (1024 ** 3), 2)
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
    except Exception:
        return None


def _make_chat_handler(agent_runner: Optional[AgentRunner]) -> Callable[["web.Request"], Awaitable["web.Response"]]:
    async def _handle_chat_api(request: "web.Request") -> "web.Response":
        limits = get_external_limits()
        ip = _client_ip(request)

        # Body parse + size guard
        try:
            raw = await request.read()
        except Exception:
            return web.json_response({"error": "could not read body"}, status=400)
        if len(raw) > _MAX_PROMPT_BYTES:
            return web.json_response({"error": "prompt too large"}, status=413)
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return web.json_response({"error": "invalid JSON"}, status=400)
        prompt = (body.get("prompt") or body.get("message") or "").strip()
        if not prompt:
            return web.json_response({"error": "missing 'prompt'"}, status=400)
        if len(prompt) > _MAX_PROMPT_BYTES:
            return web.json_response({"error": "prompt too long"}, status=413)

        verdict = limits.check("web", ip)
        if not verdict.allowed:
            log_external_request(
                surface="web", user=ip, prompt=prompt,
                outcome=verdict.reason,
            )
            status = 429 if verdict.reason in {"rate_minute", "rate_hour"} else 503
            headers = {}
            if verdict.retry_after:
                headers["Retry-After"] = str(int(verdict.retry_after))
            return web.json_response(
                {"error": verdict.reason, "message": verdict.message},
                status=status, headers=headers,
            )

        if agent_runner is None:
            log_external_request(
                surface="web", user=ip, prompt=prompt, outcome="no_runner",
            )
            return web.json_response(
                {
                    "error": "agent_unavailable",
                    "message": "Mercury's chat runner isn't wired into the public web yet — check gateway logs.",
                },
                status=503,
            )

        with StopWatch() as sw:
            try:
                reply = await agent_runner(prompt)
                outcome = "ok"
            except Exception as exc:
                logger.exception("[web] /api/chat agent runner failed")
                reply = ""
                outcome = f"runner_error:{type(exc).__name__}"
        latency = sw.elapsed_ms

        log_external_request(
            surface="web", user=ip, prompt=prompt,
            latency_ms=latency, outcome=outcome,
        )
        if outcome != "ok":
            return web.json_response(
                {"error": outcome, "message": "Mercury hit an error generating a reply.  Try again in a moment."},
                status=502,
            )
        return web.json_response({"reply": reply, "latency_ms": round(latency, 1)})

    return _handle_chat_api


async def _handle_kill_switch(request: "web.Request") -> "web.Response":
    """POST /api/external-limits/kill — toggles the external kill switch.

    Requires header ``X-Mercury-Owner: <MERCURY_OWNER_SECRET>``. If the
    env var is unset the endpoint refuses (no auth = no flip).
    """
    import os
    secret = os.environ.get("MERCURY_OWNER_SECRET", "").strip()
    presented = (request.headers.get("X-Mercury-Owner") or "").strip()
    if not secret or not presented or presented != secret:
        return web.json_response({"error": "forbidden"}, status=403)

    try:
        body = await request.json()
    except Exception:
        body = {}
    desired = body.get("enabled")
    limits = get_external_limits()
    if desired is None:
        new_value = not limits.enabled
    else:
        new_value = bool(desired)
    limits.set_enabled(new_value)
    return web.json_response({"enabled": new_value})


def register_public_web_routes(
    app: "web.Application",
    *,
    agent_runner: Optional[AgentRunner] = None,
) -> None:
    """Mount /chat, /api/chat, /api/health, /api/external-limits/kill."""
    if not AIOHTTP_AVAILABLE:
        return
    app.router.add_get("/chat", _handle_chat_html)
    app.router.add_get("/chat/", _handle_chat_html)
    app.router.add_get("/api/health", _handle_health_public)
    app.router.add_post("/api/chat", _make_chat_handler(agent_runner))
    app.router.add_post("/api/external-limits/kill", _handle_kill_switch)
