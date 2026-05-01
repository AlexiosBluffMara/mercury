"""Mercury Brain — OpenAI-compatible facade in front of Ollama.

Translates `/v1/chat/completions`, `/v1/completions`, `/v1/models` to Ollama's
native `/api/chat`, `/api/generate`, `/api/tags`. Streams via SSE in the
OpenAI delta format so any OpenAI SDK can talk to this service unmodified.

The facade owns the public port (8080); Ollama stays on localhost:11434.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("BRAIN_MODEL", "gemma4:e4b")
REQUEST_TIMEOUT = float(os.environ.get("BRAIN_REQUEST_TIMEOUT", "300"))

app = FastAPI(title="mercury-brain", version="0.1.0")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=OLLAMA_URL,
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=5.0),
        )
    return _client


# ───────────────────────────────────────────────────────────────────────── health
@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness — does the facade itself respond."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness — Ollama answers and at least one model is loaded."""
    try:
        r = await _http().get("/api/tags")
        r.raise_for_status()
        models = r.json().get("models") or []
        if not models:
            return JSONResponse({"status": "loading", "models": []}, status_code=503)
        return JSONResponse({"status": "ready", "models": [m["name"] for m in models]})
    except (httpx.HTTPError, ValueError) as exc:
        return JSONResponse({"status": "down", "error": str(exc)}, status_code=503)


# ─────────────────────────────────────────────────────────────────────── /v1/models
@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    r = await _http().get("/api/tags")
    r.raise_for_status()
    now = int(time.time())
    data = [
        {"id": m["name"], "object": "model", "created": now, "owned_by": "mercury-brain"}
        for m in (r.json().get("models") or [])
    ]
    return {"object": "list", "data": data}


# ─────────────────────────────────────────────────────────── OpenAI request schemas
class ChatMessage(BaseModel):
    role: str
    content: Any  # str | list[dict] for multimodal


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    stop: list[str] | str | None = None
    seed: int | None = None


class CompletionRequest(BaseModel):
    model: str | None = None
    prompt: str | list[str]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    stop: list[str] | str | None = None
    seed: int | None = None


# ───────────────────────────────────────────────────────────── translation helpers
def _options(req: ChatRequest | CompletionRequest) -> dict[str, Any]:
    opts: dict[str, Any] = {}
    if req.temperature is not None:
        opts["temperature"] = req.temperature
    if req.top_p is not None:
        opts["top_p"] = req.top_p
    if req.max_tokens is not None:
        opts["num_predict"] = req.max_tokens
    if req.seed is not None:
        opts["seed"] = req.seed
    if req.stop is not None:
        opts["stop"] = [req.stop] if isinstance(req.stop, str) else list(req.stop)
    return opts


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


def _sse(data: dict[str, Any] | str) -> bytes:
    payload = data if isinstance(data, str) else json.dumps(data, separators=(",", ":"))
    return f"data: {payload}\n\n".encode("utf-8")


# ────────────────────────────────────────────────────────── /v1/chat/completions
@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest) -> Any:
    model = req.model or DEFAULT_MODEL
    body = {
        "model": model,
        "messages": [m.model_dump() for m in req.messages],
        "stream": bool(req.stream),
        "options": _options(req),
        "keep_alive": "24h",
    }
    cid = _new_id("chatcmpl")
    created = int(time.time())

    if not req.stream:
        r = await _http().post("/api/chat", json=body)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        d = r.json()
        msg = d.get("message") or {}
        return {
            "id": cid,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": msg.get("role", "assistant"),
                        "content": msg.get("content", ""),
                    },
                    "finish_reason": "stop" if d.get("done") else "length",
                }
            ],
            "usage": {
                "prompt_tokens": d.get("prompt_eval_count", 0),
                "completion_tokens": d.get("eval_count", 0),
                "total_tokens": d.get("prompt_eval_count", 0) + d.get("eval_count", 0),
            },
        }

    async def gen() -> AsyncIterator[bytes]:
        try:
            async with _http().stream("POST", "/api/chat", json=body) as r:
                if r.status_code >= 400:
                    err = await r.aread()
                    yield _sse({"error": {"message": err.decode("utf-8", "ignore")}})
                    yield _sse("[DONE]")
                    return
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta_msg = chunk.get("message") or {}
                    done = bool(chunk.get("done"))
                    delta: dict[str, Any] = {}
                    if "role" in delta_msg:
                        delta["role"] = delta_msg["role"]
                    if "content" in delta_msg:
                        delta["content"] = delta_msg["content"]
                    yield _sse(
                        {
                            "id": cid,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": delta,
                                    "finish_reason": "stop" if done else None,
                                }
                            ],
                        }
                    )
        finally:
            yield _sse("[DONE]")

    return StreamingResponse(gen(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────── /v1/completions
@app.post("/v1/completions")
async def completions(req: CompletionRequest) -> Any:
    model = req.model or DEFAULT_MODEL
    prompt = req.prompt if isinstance(req.prompt, str) else "\n".join(req.prompt)
    body = {
        "model": model,
        "prompt": prompt,
        "stream": bool(req.stream),
        "options": _options(req),
        "keep_alive": "24h",
    }
    cid = _new_id("cmpl")
    created = int(time.time())

    if not req.stream:
        r = await _http().post("/api/generate", json=body)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        d = r.json()
        return {
            "id": cid,
            "object": "text_completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "text": d.get("response", ""),
                    "finish_reason": "stop" if d.get("done") else "length",
                }
            ],
            "usage": {
                "prompt_tokens": d.get("prompt_eval_count", 0),
                "completion_tokens": d.get("eval_count", 0),
                "total_tokens": d.get("prompt_eval_count", 0) + d.get("eval_count", 0),
            },
        }

    async def gen() -> AsyncIterator[bytes]:
        try:
            async with _http().stream("POST", "/api/generate", json=body) as r:
                if r.status_code >= 400:
                    err = await r.aread()
                    yield _sse({"error": {"message": err.decode("utf-8", "ignore")}})
                    yield _sse("[DONE]")
                    return
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield _sse(
                        {
                            "id": cid,
                            "object": "text_completion",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "text": chunk.get("response", ""),
                                    "finish_reason": "stop" if chunk.get("done") else None,
                                }
                            ],
                        }
                    )
        finally:
            yield _sse("[DONE]")

    return StreamingResponse(gen(), media_type="text/event-stream")


# ─────────────────────────────────────────────── pass-through for native Ollama
@app.api_route("/api/{path:path}", methods=["GET", "POST"])
async def ollama_passthrough(path: str, request: Request) -> Any:
    """Forward Ollama-native calls untouched (lets Mercury opt out of OpenAI translation)."""
    body = await request.body()
    headers = {"content-type": request.headers.get("content-type", "application/json")}
    r = await _http().request(
        request.method,
        f"/api/{path}",
        content=body,
        headers=headers,
        params=request.query_params,
    )
    return JSONResponse(
        content=r.json() if r.headers.get("content-type", "").startswith("application/json")
        else {"raw": r.text},
        status_code=r.status_code,
    )


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _client is not None:
        await _client.aclose()
