"""Thin OpenAI-compatible client for the Mercury brain container.

In Cloud Run mode Mercury (the gateway / agent loop) talks to a separate
"brain" service that hosts the Gemma SKUs. The brain speaks the
OpenAI-compatible chat-completions protocol, so this client is small:
build the request, retry on 5xx, stream chunks back, log to the existing
external-request JSONL log.

Local dev defaults to ``http://localhost:11434/v1`` so devs can point at
a local Ollama instance with the OpenAI shim enabled.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore[assignment]
    HTTPX_AVAILABLE = False

from gateway.external_logging import log_external_request


logger = logging.getLogger(__name__)

DEFAULT_BRAIN_URL = "http://localhost:11434/v1"
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_RETRIES = 3
RETRY_BACKOFF_BASE_S = 0.5


def _brain_url() -> str:
    return (os.environ.get("BRAIN_URL") or DEFAULT_BRAIN_URL).rstrip("/")


def _api_key() -> str:
    return os.environ.get("BRAIN_API_KEY", "").strip()


@dataclass
class BrainCallStats:
    model: str
    latency_ms: float
    token_count: int
    user_id: str | None
    outcome: str


class BrainClient:
    """Async OpenAI-compatible client with retries + JSONL logging.

    Reuses one ``httpx.AsyncClient`` per instance. Construct one per
    process and share it; safe under asyncio concurrency.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_RETRIES,
    ) -> None:
        if not HTTPX_AVAILABLE:
            raise RuntimeError("brain_client requires httpx — install with `uv pip install httpx`")
        self._base_url = (base_url or _brain_url()).rstrip("/")
        self._api_key = api_key if api_key is not None else _api_key()
        self._timeout_s = timeout_s
        self._max_retries = max(0, int(max_retries))
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> "httpx.AsyncClient":
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout_s,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        options: dict[str, Any] | None = None,
        *,
        user_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream token chunks from the brain's chat-completions endpoint.

        Yields plain string deltas (no SSE framing). Caller concatenates.
        """
        opts = dict(options or {})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        for k in ("temperature", "top_p", "max_tokens", "stop", "think", "num_ctx"):
            if k in opts:
                payload[k] = opts[k]

        return self._chat_stream(payload, user_id=user_id)

    async def _chat_stream(
        self,
        payload: dict[str, Any],
        *,
        user_id: str | None,
    ) -> AsyncIterator[str]:
        model = payload.get("model", "")
        start = time.perf_counter()
        token_count = 0
        outcome = "ok"
        client = await self._ensure_client()

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with client.stream("POST", "/chat/completions", json=payload) as resp:
                    if resp.status_code >= 500:
                        await resp.aread()
                        raise httpx.HTTPStatusError(
                            f"brain {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", errors="replace")
                        outcome = f"http_{resp.status_code}"
                        logger.warning("[brain_client] %s body=%s", outcome, body[:400])
                        return
                    async for chunk in self._iter_sse_deltas(resp):
                        token_count += 1
                        yield chunk
                break
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    outcome = f"error:{type(exc).__name__}"
                    break
                await asyncio.sleep(RETRY_BACKOFF_BASE_S * (2 ** attempt))
            except Exception as exc:
                last_exc = exc
                outcome = f"error:{type(exc).__name__}"
                break

        latency_ms = (time.perf_counter() - start) * 1000.0
        log_external_request(
            surface="brain",
            user=user_id or "unknown",
            prompt="",
            latency_ms=latency_ms,
            model=model,
            outcome=outcome,
            extra={"tokens": token_count, "url": self._base_url},
        )
        if outcome != "ok" and last_exc is not None:
            logger.warning("[brain_client] %s after %d attempts: %s",
                           outcome, attempt + 1, last_exc)

    @staticmethod
    async def _iter_sse_deltas(resp: "httpx.Response") -> AsyncIterator[str]:
        async for line in resp.aiter_lines():
            if not line:
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data = line[5:].strip()
            else:
                data = line.strip()
            if not data or data == "[DONE]":
                if data == "[DONE]":
                    return
                continue
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content


_default_client: BrainClient | None = None
_default_lock = asyncio.Lock()


async def get_default_client() -> BrainClient:
    """Return a process-wide singleton brain client."""
    global _default_client
    if _default_client is not None:
        return _default_client
    async with _default_lock:
        if _default_client is None:
            _default_client = BrainClient()
    return _default_client


def reset_default_client_for_tests() -> None:
    global _default_client
    _default_client = None


__all__ = [
    "DEFAULT_BRAIN_URL",
    "BrainCallStats",
    "BrainClient",
    "get_default_client",
    "reset_default_client_for_tests",
]
