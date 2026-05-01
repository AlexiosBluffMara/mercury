"""Tests for the brain HTTP client (mocked httpx transport)."""
from __future__ import annotations

import json

import httpx
import pytest

from agent import brain_client


pytestmark = pytest.mark.asyncio


def _sse_body(chunks: list[str]) -> bytes:
    lines = []
    for c in chunks:
        payload = {"choices": [{"delta": {"content": c}}]}
        lines.append(f"data: {json.dumps(payload)}")
    lines.append("data: [DONE]")
    return ("\n".join(lines) + "\n").encode("utf-8")


@pytest.fixture(autouse=True)
def _reset_default_client():
    brain_client.reset_default_client_for_tests()
    yield
    brain_client.reset_default_client_for_tests()


async def test_chat_streams_deltas(monkeypatch):
    expected = ["Hello", " ", "world", "!"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == "gemma3:e4b"
        assert body["stream"] is True
        return httpx.Response(
            200,
            content=_sse_body(expected),
            headers={"Content-Type": "text/event-stream"},
        )

    transport = httpx.MockTransport(handler)
    client = brain_client.BrainClient(base_url="http://brain.test/v1")
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="http://brain.test/v1",
        headers={"Content-Type": "application/json"},
    )

    received: list[str] = []
    stream = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="gemma3:e4b",
        user_id="123",
    )
    async for chunk in stream:
        received.append(chunk)
    await client.close()

    assert received == expected


async def test_chat_retries_on_5xx(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(
            200,
            content=_sse_body(["ok"]),
            headers={"Content-Type": "text/event-stream"},
        )

    transport = httpx.MockTransport(handler)
    client = brain_client.BrainClient(base_url="http://brain.test/v1", max_retries=3)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="http://brain.test/v1",
        headers={"Content-Type": "application/json"},
    )

    out: list[str] = []
    stream = await client.chat([{"role": "user", "content": "x"}], "m")
    async for chunk in stream:
        out.append(chunk)
    await client.close()

    assert out == ["ok"]
    assert calls["n"] == 3


async def test_chat_4xx_returns_no_chunks_no_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, text="bad request")

    transport = httpx.MockTransport(handler)
    client = brain_client.BrainClient(base_url="http://brain.test/v1", max_retries=3)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="http://brain.test/v1",
        headers={"Content-Type": "application/json"},
    )

    out: list[str] = []
    stream = await client.chat([{"role": "user", "content": "x"}], "m")
    async for chunk in stream:
        out.append(chunk)
    await client.close()

    assert out == []
    assert calls["n"] == 1


async def test_default_brain_url(monkeypatch):
    monkeypatch.delenv("BRAIN_URL", raising=False)
    c = brain_client.BrainClient()
    assert c._base_url == brain_client.DEFAULT_BRAIN_URL.rstrip("/")


async def test_brain_url_from_env(monkeypatch):
    monkeypatch.setenv("BRAIN_URL", "https://brain.example.com/v1/")
    c = brain_client.BrainClient()
    assert c._base_url == "https://brain.example.com/v1"


async def test_options_passthrough(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            content=_sse_body(["x"]),
            headers={"Content-Type": "text/event-stream"},
        )

    transport = httpx.MockTransport(handler)
    client = brain_client.BrainClient(base_url="http://brain.test/v1")
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="http://brain.test/v1",
        headers={"Content-Type": "application/json"},
    )

    stream = await client.chat(
        messages=[{"role": "user", "content": "x"}],
        model="m",
        options={"temperature": 0.7, "max_tokens": 200, "think": True, "ignored_key": 1},
    )
    async for _ in stream:
        pass
    await client.close()

    assert captured["temperature"] == 0.7
    assert captured["max_tokens"] == 200
    assert captured["think"] is True
    assert "ignored_key" not in captured
