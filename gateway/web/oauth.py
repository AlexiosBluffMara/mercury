"""Discord OAuth + signed-cookie session for the Mercury web surface.

Three routes get registered onto the existing aiohttp app:

* ``GET  /login``           — redirect to Discord's authorize URL
* ``GET  /oauth/callback``  — exchange code, fetch profile, set cookie
* ``POST /logout``          — clear the cookie

The cookie is encrypted via ``aiohttp_session.EncryptedCookieStorage``
keyed off ``SESSION_SECRET_KEY`` (32 random bytes, hex-encoded). The
session payload is ``{"user_id": "<discord_snowflake>", "display_name":
"...", "expires_at": <unix>}``.

If ``aiohttp_session`` or ``cryptography`` aren't installed, registration
is a no-op and the existing anonymous-cookie path keeps working.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets as _secrets
import time
from typing import Any
from urllib.parse import urlencode

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None  # type: ignore[assignment]

try:
    import aiohttp_session
    from aiohttp_session import get_session, new_session, session_middleware
    from aiohttp_session.cookie_storage import EncryptedCookieStorage
    SESSION_AVAILABLE = True
except ImportError:
    SESSION_AVAILABLE = False
    aiohttp_session = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
SESSION_TTL_S = 30 * 24 * 3600  # 30 days


def _client_id() -> str:
    return os.environ.get("DISCORD_CLIENT_ID", "").strip()


def _client_secret() -> str:
    return os.environ.get("DISCORD_CLIENT_SECRET", "").strip()


def _redirect_uri() -> str:
    return os.environ.get("OAUTH_REDIRECT_URI", "").strip()


def _session_secret() -> bytes:
    raw = os.environ.get("SESSION_SECRET_KEY", "").strip()
    if raw:
        # Accept hex (64 chars) or raw 32-byte base64.
        try:
            if len(raw) == 64:
                return bytes.fromhex(raw)
            return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))[:32]
        except (ValueError, base64.binascii.Error):
            pass
    # Dev fallback — non-persistent. Logs a warning so prod misuse is loud.
    logger.warning(
        "[oauth] SESSION_SECRET_KEY missing or invalid — generating ephemeral key. "
        "Sessions will not survive a restart."
    )
    return _secrets.token_bytes(32)


def install_session_middleware(app: "web.Application") -> bool:
    """Attach `aiohttp_session` middleware to ``app`` if available.

    Idempotent: a second call does nothing. Returns True on success.
    """
    if not SESSION_AVAILABLE or not AIOHTTP_AVAILABLE:
        logger.info("[oauth] aiohttp_session not installed — skipping session middleware")
        return False
    if app.get("_mercury_session_installed"):
        return True
    storage = EncryptedCookieStorage(
        _session_secret(),
        cookie_name="mercury_session",
        max_age=SESSION_TTL_S,
        httponly=True,
        samesite="Lax",
    )
    app.middlewares.append(session_middleware(storage))
    app["_mercury_session_installed"] = True
    return True


async def _handle_login(request: "web.Request") -> "web.Response":
    cid = _client_id()
    redir = _redirect_uri()
    if not cid or not redir:
        return web.Response(status=503, text="Discord OAuth not configured")
    state = _secrets.token_urlsafe(24)
    session = await new_session(request) if SESSION_AVAILABLE else None
    if session is not None:
        session["oauth_state"] = state
    params = {
        "response_type": "code",
        "client_id": cid,
        "scope": "identify",
        "redirect_uri": redir,
        "state": state,
        "prompt": "none",
    }
    return web.HTTPFound(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")


async def _handle_oauth_callback(request: "web.Request") -> "web.Response":
    code = request.query.get("code", "").strip()
    state = request.query.get("state", "").strip()
    if not code:
        return web.Response(status=400, text="missing code")

    if SESSION_AVAILABLE:
        session = await get_session(request)
        expected_state = session.get("oauth_state")
        if not expected_state or expected_state != state:
            return web.Response(status=400, text="state mismatch")
        session.pop("oauth_state", None)
    else:
        session = None

    cid = _client_id()
    secret = _client_secret()
    redir = _redirect_uri()
    if not cid or not secret or not redir:
        return web.Response(status=503, text="Discord OAuth not configured")

    try:
        import aiohttp
    except ImportError:
        return web.Response(status=503, text="aiohttp not available")

    token_payload = {
        "client_id": cid,
        "client_secret": secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redir,
    }
    async with aiohttp.ClientSession() as http:
        async with http.post(
            DISCORD_TOKEN_URL,
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            if r.status != 200:
                body = (await r.text())[:300]
                logger.warning("[oauth] token exchange failed: %s %s", r.status, body)
                return web.Response(status=502, text="oauth token exchange failed")
            tok = await r.json()
        access = tok.get("access_token", "")
        if not access:
            return web.Response(status=502, text="no access_token")

        async with http.get(
            DISCORD_USER_URL,
            headers={"Authorization": f"Bearer {access}"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            if r.status != 200:
                return web.Response(status=502, text="oauth profile fetch failed")
            prof = await r.json()

    user_id = str(prof.get("id") or "").strip()
    display = (prof.get("global_name") or prof.get("username") or "").strip() or None
    if not user_id:
        return web.Response(status=502, text="oauth profile missing id")

    if session is not None:
        session["user_id"] = user_id
        session["display_name"] = display
        session["expires_at"] = int(time.time()) + SESSION_TTL_S

    return web.HTTPFound("/chat")


async def _handle_logout(request: "web.Request") -> "web.Response":
    if SESSION_AVAILABLE:
        session = await get_session(request)
        session.invalidate()
    return web.json_response({"ok": True})


async def get_session_user(request: "web.Request") -> dict[str, Any] | None:
    """Return ``{"user_id", "display_name"}`` if the request is logged-in,
    otherwise None. Anonymous sessions are handled by the caller (assign
    an ``anon_<hex>`` and stash it back into the session)."""
    if not SESSION_AVAILABLE:
        return None
    session = await get_session(request)
    uid = session.get("user_id")
    if not uid:
        return None
    exp = session.get("expires_at")
    if exp and int(exp) < int(time.time()):
        session.invalidate()
        return None
    return {"user_id": str(uid), "display_name": session.get("display_name")}


async def get_or_assign_anon_id(request: "web.Request") -> str:
    """Return the anon-ID for this session, creating one if needed."""
    from agent.tenancy import make_anonymous_id

    if not SESSION_AVAILABLE:
        return make_anonymous_id()
    session = await get_session(request)
    uid = session.get("user_id")
    if uid:
        return str(uid)
    aid = session.get("anon_id")
    if not aid:
        aid = make_anonymous_id()
        session["anon_id"] = aid
    return str(aid)


def register_oauth_routes(app: "web.Application") -> None:
    """Mount /login, /oauth/callback, /logout. Idempotent."""
    if not AIOHTTP_AVAILABLE:
        return
    if app.get("_mercury_oauth_installed"):
        return
    install_session_middleware(app)
    app.router.add_get("/login", _handle_login)
    app.router.add_get("/oauth/callback", _handle_oauth_callback)
    app.router.add_post("/logout", _handle_logout)
    app["_mercury_oauth_installed"] = True


__all__ = [
    "get_or_assign_anon_id",
    "get_session_user",
    "install_session_middleware",
    "register_oauth_routes",
]
