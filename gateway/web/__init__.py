"""Public web surface for Mercury — chat UI + /api/chat + /api/health.

This package is wired into the existing aiohttp app from
`gateway/platforms/api_server.py` via `register_public_web_routes`.
The intent is additive: the existing `/v1/chat/completions` and
`/health` endpoints continue to work; this module adds a separate
`/api/chat` (rate-limited, public) and `/api/health` (cost / GPU
status) plus the `/chat` static page.

See `docs/EXTERNAL_LIMITS.md` for the rate-limit / kill-switch /
daily-cap configuration.
"""

from .routes import register_public_web_routes

__all__ = ["register_public_web_routes"]
