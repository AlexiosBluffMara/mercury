"""Mercury-specific FastAPI routes and middleware.

Mounted onto the existing dashboard FastAPI app via:

    from mercury_cli.mercury_routes import mercury_router, TailscaleIdentityMiddleware
    app.include_router(mercury_router)
    app.add_middleware(TailscaleIdentityMiddleware)

All endpoints live under `/api/mercury/*` so they don't collide with
upstream routes.  Read-only by default — preference toggles are
session-scoped and don't persist.

The Tailscale middleware is a pass-through: it parses the
`Tailscale-User-{Login,Name,Profile-Pic}` headers Tailscale injects
on every request reached via `tailscale serve`, and stashes a
`TailnetIdentity` on `request.state.tailnet_identity`.  It does not
reject requests on its own — the existing dashboard session-token
auth still gates write operations.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from mercury import copilot_models as cm
from mercury import cortex_bridge, tailscale

logger = logging.getLogger(__name__)

mercury_router = APIRouter(prefix="/api/mercury", tags=["mercury"])


def _model_to_dict(m: cm.ModelDescriptor) -> dict[str, Any]:
    return {
        "model_id": m.model_id,
        "provider": m.provider,
        "multiplier": m.multiplier,
        "api_mode": m.api_mode,
        "supports_vision": m.supports_vision,
        "supports_tools": m.supports_tools,
        "note": m.note,
    }


@mercury_router.get("/brains")
def get_brains(request: Request) -> dict[str, Any]:
    """Catalog + live state for the BrainsPage UI."""
    cortex_report = cortex_bridge.cortex_vram_report()
    cortex_state = cortex_bridge.cortex_state()

    ts_status = tailscale.status()
    ts_running = tailscale.is_running()
    ts_hostname = tailscale.hostname()
    ts_dns = tailscale.magic_dns_name()

    identity = getattr(request.state, "tailnet_identity", None)
    identity_dict: dict[str, str] | None
    if identity is not None:
        identity_dict = {
            "login": identity.login,
            "name": identity.name,
            "profile_picture": identity.profile_picture or "",
        }
    else:
        identity_dict = None

    return {
        "catalog": {
            "zero_premium": [_model_to_dict(m) for m in cm.ZERO_PREMIUM_MODELS],
            "part_time": [_model_to_dict(m) for m in cm.LOCAL_MODELS],
            "escalation": [_model_to_dict(m) for m in cm.ESCALATION_MODELS],
        },
        "defaults": {
            "fulltime": _model_to_dict(cm.DEFAULT_FULLTIME_BRAIN),
            "vision": _model_to_dict(cm.DEFAULT_VISION_BRAIN),
            "part_time": _model_to_dict(cm.DEFAULT_PARTTIME_BRAIN),
            "code_escalation": _model_to_dict(cm.DEFAULT_CODE_ESCALATION),
            "reasoning_escalation": _model_to_dict(cm.DEFAULT_REASONING_ESCALATION),
        },
        "cortex": {
            "available": cortex_report.get("available", False),
            "state": cortex_state,
            "vram": cortex_report,
        },
        "tailscale": {
            "installed": tailscale.is_installed(),
            "running": ts_running,
            "hostname": ts_hostname,
            "magic_dns": ts_dns,
            "tailnet_ip": tailscale.tailnet_ip(),
            "backend_state": (ts_status or {}).get("BackendState"),
        },
        "identity": identity_dict,
        "preference": "auto",
    }


@mercury_router.get("/cortex/state")
def get_cortex_state() -> dict[str, Any]:
    return {
        "available": cortex_bridge.cortex_available(),
        "state": cortex_bridge.cortex_state(),
        "tribe_running": cortex_bridge.tribe_running(),
        "vram": cortex_bridge.cortex_vram_report(),
    }


@mercury_router.get("/tailscale")
def get_tailscale(request: Request) -> dict[str, Any]:
    identity = getattr(request.state, "tailnet_identity", None)
    return {
        "installed": tailscale.is_installed(),
        "running": tailscale.is_running(),
        "hostname": tailscale.hostname(),
        "magic_dns": tailscale.magic_dns_name(),
        "tailnet_ip": tailscale.tailnet_ip(),
        "webui_url": tailscale.webui_url(),
        "identity": (
            {
                "login": identity.login,
                "name": identity.name,
                "profile_picture": identity.profile_picture or "",
            }
            if identity is not None
            else None
        ),
    }


class TailscaleIdentityMiddleware(BaseHTTPMiddleware):
    """Parse Tailscale identity headers and attach to request.state.

    The `Tailscale-User-{Login,Name,Profile-Pic}` headers are injected by
    Tailscale's local proxy when the WebUI is reached via
    `tailscale serve`.  Mercury treats them as the identity layer in
    place of a separate password — the tailnet ACL is the actual
    authorization boundary.

    This middleware is read-only — it never rejects.  It's the
    upstream session-token auth that gates writes.  We just give
    routes a way to know who's calling.
    """

    async def dispatch(self, request: Request, call_next):
        identity = tailscale.extract_identity(dict(request.headers))
        request.state.tailnet_identity = identity
        return await call_next(request)
