"""Tests for the multi-tenant context module (in-memory fallback path)."""
from __future__ import annotations

import pytest

from agent import tenancy


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch):
    monkeypatch.delenv("MERCURY_MODE", raising=False)
    monkeypatch.delenv("FIRESTORE_PROJECT", raising=False)
    tenancy.reset_in_memory_store_for_tests()
    yield
    tenancy.reset_in_memory_store_for_tests()


async def test_load_tenant_known_user_uses_default_quota():
    ctx = await tenancy.load_tenant("123456789012345678")
    assert ctx.user_id == "123456789012345678"
    assert ctx.is_anonymous is False
    assert ctx.daily_quota == tenancy.DEFAULT_KNOWN_QUOTA
    assert ctx.daily_used == 0


async def test_load_tenant_anonymous_gets_lower_quota():
    aid = tenancy.make_anonymous_id()
    assert aid.startswith(tenancy.ANON_PREFIX)
    ctx = await tenancy.load_tenant(aid)
    assert ctx.is_anonymous is True
    assert ctx.daily_quota == tenancy.DEFAULT_ANON_QUOTA


async def test_save_event_increments_daily_used():
    ctx = await tenancy.load_tenant("999")
    await tenancy.save_tenant_event(ctx, {"kind": "chat", "tokens": 250})
    await tenancy.save_tenant_event(ctx, {"kind": "chat", "tokens": 100})
    # Reload to confirm persistence in the in-memory store.
    ctx2 = await tenancy.load_tenant("999")
    assert ctx2.daily_used == 350


async def test_quota_helpers():
    ctx = await tenancy.load_tenant("777")
    ctx.daily_used = ctx.daily_quota - 10
    assert tenancy.quota_remaining(ctx) == 10
    assert tenancy.quota_exceeded(ctx) is False
    ctx.daily_used = ctx.daily_quota + 5
    assert tenancy.quota_remaining(ctx) == 0
    assert tenancy.quota_exceeded(ctx) is True


async def test_memory_roundtrip():
    ctx = await tenancy.load_tenant("555")
    await tenancy.update_tenant_memory(ctx, "favorite_color", "blue")
    await tenancy.update_tenant_memory(ctx, "timezone", "America/Chicago")
    mem = await tenancy.get_tenant_memory(ctx)
    assert mem == {"favorite_color": "blue", "timezone": "America/Chicago"}


async def test_anonymous_memory_isolated_from_known_user():
    a = await tenancy.load_tenant(tenancy.make_anonymous_id())
    b = await tenancy.load_tenant("known-user-1")
    await tenancy.update_tenant_memory(a, "k", "anon")
    await tenancy.update_tenant_memory(b, "k", "known")
    assert (await tenancy.get_tenant_memory(a))["k"] == "anon"
    assert (await tenancy.get_tenant_memory(b))["k"] == "known"


async def test_firestore_unavailable_when_mode_local(monkeypatch):
    monkeypatch.setenv("MERCURY_MODE", "local")
    monkeypatch.setenv("FIRESTORE_PROJECT", "abm-isu")
    assert tenancy._firestore_available() is False


async def test_firestore_unavailable_without_project(monkeypatch):
    monkeypatch.setenv("MERCURY_MODE", "cloud")
    monkeypatch.delenv("FIRESTORE_PROJECT", raising=False)
    assert tenancy._firestore_available() is False


async def test_is_anonymous_id():
    assert tenancy.is_anonymous_id("anon_abcd1234") is True
    assert tenancy.is_anonymous_id("123456789") is False
