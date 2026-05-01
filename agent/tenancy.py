"""Per-user tenant context for multi-tenant Mercury (Cloud Run mode).

Identity = Discord user-ID snowflake (e.g. ``"123456789012345678"``). Web
sessions backed by Discord OAuth share that ID; anonymous web sessions
get a temporary ``anon_<8hex>`` ID with a smaller daily quota and no
persistence beyond the session.

State layout in Firestore::

    users/{user_id}/
        profile          (doc)  display_name, timezone, registered_at,
                                last_seen, opted_in_research, daily_quota_used
        preferences      (doc)  reasoning_mode, gemma_sku, content_tier_prefs
        memory/{key}     (subcoll) long-term KV pairs
        conversations/   (subcoll) one doc per session with messages array

Local mode (``MERCURY_MODE=local``, the default, or no Firestore creds)
keeps everything in process-local dicts so devs can run Mercury without a
GCP project. Cloud mode (``MERCURY_MODE=cloud`` plus
``FIRESTORE_PROJECT``) reads/writes Firestore.
"""

from __future__ import annotations

import os
import secrets
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DEFAULT_KNOWN_QUOTA = 100_000
DEFAULT_ANON_QUOTA = 5_000
ANON_PREFIX = "anon_"


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class TenantContext:
    user_id: str
    is_anonymous: bool
    display_name: str | None = None
    daily_quota: int = DEFAULT_KNOWN_QUOTA
    daily_used: int = 0
    timezone: str | None = None
    preferences: dict[str, Any] = field(default_factory=dict)


def _mode() -> str:
    return os.environ.get("MERCURY_MODE", "local").strip().lower() or "local"


def _firestore_available() -> bool:
    if _mode() != "cloud":
        return False
    if not os.environ.get("FIRESTORE_PROJECT"):
        return False
    try:
        import google.cloud.firestore  # noqa: F401
    except ImportError:
        return False
    return True


def make_anonymous_id() -> str:
    return f"{ANON_PREFIX}{secrets.token_hex(4)}"


def is_anonymous_id(user_id: str) -> bool:
    return user_id.startswith(ANON_PREFIX)


# ─────────────────────────────────────────────────────────────────────────────
# In-memory store (local dev + anonymous sessions)
# ─────────────────────────────────────────────────────────────────────────────


class _InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._profiles: dict[str, dict[str, Any]] = {}
        self._memory: dict[str, dict[str, Any]] = defaultdict(dict)
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._daily_used: dict[str, int] = defaultdict(int)
        self._daily_date: str = _utc_today()

    def _maybe_roll(self) -> None:
        today = _utc_today()
        if today != self._daily_date:
            self._daily_date = today
            self._daily_used.clear()

    def get_profile(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            self._maybe_roll()
            prof = dict(self._profiles.get(user_id, {}))
            prof["daily_used"] = self._daily_used.get(user_id, 0)
            return prof

    def upsert_profile(self, user_id: str, fields: dict[str, Any]) -> None:
        with self._lock:
            existing = self._profiles.setdefault(user_id, {})
            existing.update(fields)

    def append_event(self, user_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            self._events[user_id].append(event)
            tokens = int(event.get("tokens") or 0)
            if tokens:
                self._maybe_roll()
                self._daily_used[user_id] += tokens

    def get_memory(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._memory.get(user_id, {}))

    def update_memory(self, user_id: str, key: str, value: Any) -> None:
        with self._lock:
            self._memory[user_id][key] = value


_memory_store = _InMemoryStore()


# ─────────────────────────────────────────────────────────────────────────────
# Firestore-backed store (cloud mode)
# ─────────────────────────────────────────────────────────────────────────────


_firestore_client = None
_firestore_lock = threading.Lock()


def _get_firestore():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    with _firestore_lock:
        if _firestore_client is not None:
            return _firestore_client
        from google.cloud import firestore  # type: ignore[import-not-found]
        project = os.environ.get("FIRESTORE_PROJECT")
        _firestore_client = firestore.AsyncClient(project=project)
    return _firestore_client


async def _firestore_get_profile(user_id: str) -> dict[str, Any]:
    client = _get_firestore()
    doc = await client.collection("users").document(user_id).collection("_meta").document("profile").get()
    return doc.to_dict() or {} if doc.exists else {}


async def _firestore_upsert_profile(user_id: str, fields: dict[str, Any]) -> None:
    client = _get_firestore()
    ref = client.collection("users").document(user_id).collection("_meta").document("profile")
    await ref.set(fields, merge=True)


async def _firestore_append_event(user_id: str, event: dict[str, Any]) -> None:
    client = _get_firestore()
    ref = client.collection("users").document(user_id).collection("events").document()
    await ref.set(event)
    tokens = int(event.get("tokens") or 0)
    if tokens:
        from google.cloud.firestore import Increment  # type: ignore[import-not-found]
        prof_ref = client.collection("users").document(user_id).collection("_meta").document("profile")
        await prof_ref.set(
            {"daily_used": Increment(tokens), "daily_used_date": _utc_today()},
            merge=True,
        )


async def _firestore_get_memory(user_id: str) -> dict[str, Any]:
    client = _get_firestore()
    out: dict[str, Any] = {}
    async for doc in client.collection("users").document(user_id).collection("memory").stream():
        data = doc.to_dict() or {}
        out[doc.id] = data.get("value")
    return out


async def _firestore_update_memory(user_id: str, key: str, value: Any) -> None:
    client = _get_firestore()
    ref = client.collection("users").document(user_id).collection("memory").document(key)
    await ref.set({"value": value, "updated_at": _utcnow_iso()})


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def load_tenant(user_id: str) -> TenantContext:
    """Load (or lazily create) a tenant context for ``user_id``.

    Anonymous IDs (``anon_<hex>``) get the smaller default quota and are
    never persisted to Firestore, even in cloud mode.
    """
    is_anon = is_anonymous_id(user_id)
    quota = DEFAULT_ANON_QUOTA if is_anon else DEFAULT_KNOWN_QUOTA

    if is_anon or not _firestore_available():
        prof = _memory_store.get_profile(user_id)
        if not prof:
            _memory_store.upsert_profile(
                user_id,
                {
                    "registered_at": _utcnow_iso(),
                    "last_seen": _utcnow_iso(),
                },
            )
            prof = _memory_store.get_profile(user_id)
        else:
            _memory_store.upsert_profile(user_id, {"last_seen": _utcnow_iso()})
        return TenantContext(
            user_id=user_id,
            is_anonymous=is_anon,
            display_name=prof.get("display_name"),
            daily_quota=quota,
            daily_used=int(prof.get("daily_used") or 0),
            timezone=prof.get("timezone"),
            preferences=dict(prof.get("preferences") or {}),
        )

    prof = await _firestore_get_profile(user_id)
    if not prof:
        await _firestore_upsert_profile(
            user_id,
            {"registered_at": _utcnow_iso(), "last_seen": _utcnow_iso()},
        )
        prof = {"registered_at": _utcnow_iso(), "last_seen": _utcnow_iso()}
    else:
        await _firestore_upsert_profile(user_id, {"last_seen": _utcnow_iso()})

    daily_used = 0
    if prof.get("daily_used_date") == _utc_today():
        daily_used = int(prof.get("daily_used") or 0)
    return TenantContext(
        user_id=user_id,
        is_anonymous=False,
        display_name=prof.get("display_name"),
        daily_quota=quota,
        daily_used=daily_used,
        timezone=prof.get("timezone"),
        preferences=dict(prof.get("preferences") or {}),
    )


async def save_tenant_event(ctx: TenantContext, event: dict[str, Any]) -> None:
    """Append an event (chat turn, model call, etc.) for this tenant.

    The event dict may contain ``tokens`` — when present, that count is
    added to the tenant's daily-used counter.
    """
    payload = dict(event)
    payload.setdefault("ts", _utcnow_iso())

    if ctx.is_anonymous or not _firestore_available():
        _memory_store.append_event(ctx.user_id, payload)
        ctx.daily_used = _memory_store.get_profile(ctx.user_id).get("daily_used", 0) or ctx.daily_used + int(payload.get("tokens") or 0)
        return

    await _firestore_append_event(ctx.user_id, payload)
    ctx.daily_used += int(payload.get("tokens") or 0)


async def get_tenant_memory(ctx: TenantContext) -> dict[str, Any]:
    """Return all long-term memory KV pairs for this tenant."""
    if ctx.is_anonymous or not _firestore_available():
        return _memory_store.get_memory(ctx.user_id)
    return await _firestore_get_memory(ctx.user_id)


async def update_tenant_memory(ctx: TenantContext, key: str, value: Any) -> None:
    """Set one memory KV pair. Anonymous tenants keep memory in-process
    only — it disappears with the gateway restart."""
    if ctx.is_anonymous or not _firestore_available():
        _memory_store.update_memory(ctx.user_id, key, value)
        return
    await _firestore_update_memory(ctx.user_id, key, value)


def quota_remaining(ctx: TenantContext) -> int:
    """Tokens left in the current UTC day for this tenant."""
    return max(0, ctx.daily_quota - ctx.daily_used)


def quota_exceeded(ctx: TenantContext) -> bool:
    return ctx.daily_used >= ctx.daily_quota


def reset_in_memory_store_for_tests() -> None:
    """Clear the process-local store. Cloud Firestore is untouched."""
    global _memory_store
    _memory_store = _InMemoryStore()


__all__ = [
    "ANON_PREFIX",
    "DEFAULT_ANON_QUOTA",
    "DEFAULT_KNOWN_QUOTA",
    "TenantContext",
    "get_tenant_memory",
    "is_anonymous_id",
    "load_tenant",
    "make_anonymous_id",
    "quota_exceeded",
    "quota_remaining",
    "reset_in_memory_store_for_tests",
    "save_tenant_event",
    "update_tenant_memory",
]
