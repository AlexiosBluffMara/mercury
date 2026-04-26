"""Unified google-genai client factory for Mercury.

Google consolidated the Gemini API and Vertex AI behind the same SDK
(`google-genai`) at Cloud Next 2026 — Vertex AI was rebranded to
"Gemini Enterprise Agent Platform".  Mercury exposes both behind one
factory so callers don't care which mode is active:

  - **AI Studio** (`mode="ai_studio"`): free-tier dev key from
    aistudio.google.com.  Heavily rate-limited (Gemini Flash now 20
    RPD on free as of 2026-01-31), useful only for prototyping.

  - **Vertex** (`mode="vertex"`): production path with billing + IAM
    via gcloud Application Default Credentials.  Requires
    GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION env vars (or
    explicit kwargs).

  - **auto** (default): picks Vertex when GOOGLE_GENAI_USE_VERTEXAI
    is true OR ADC is available, otherwise falls back to AI Studio.

Both modes return the same `google.genai.Client` instance — call
`.models.generate_content(...)` on it identically.
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from google import genai

logger = logging.getLogger(__name__)

GenAIMode = Literal["ai_studio", "vertex", "auto"]

DEFAULT_VERTEX_LOCATION = "us-central1"


def _read_api_key() -> str | None:
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_STUDIO_API_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def _vertex_envs_set() -> bool:
    flag = (os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") or "").strip().lower()
    if flag in ("true", "1", "yes"):
        return True
    if flag in ("false", "0", "no"):
        return False
    return bool((os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip())


def detect_mode() -> GenAIMode:
    """Default to Vertex when GOOGLE_CLOUD_PROJECT is set OR
    GOOGLE_GENAI_USE_VERTEXAI=true.  Mercury runs under the
    philanthropytraders.com Workspace org, which forbids API keys at
    org-policy level — Vertex/ADC is the only path that works for
    GCP-resourced calls.  AI Studio remains a fallback for personal-key
    flows (e.g. when working off-org)."""
    if _vertex_envs_set():
        return "vertex"
    if _read_api_key():
        return "ai_studio"
    return "vertex"


def make_client(
    mode: GenAIMode = "auto",
    *,
    api_key: str | None = None,
    project: str | None = None,
    location: str | None = None,
) -> genai.Client:
    """Return a configured `google.genai.Client`.

    Raises ValueError if the requested mode lacks credentials.
    """
    resolved: GenAIMode = detect_mode() if mode == "auto" else mode

    if resolved == "ai_studio":
        key = api_key or _read_api_key()
        if not key:
            raise ValueError(
                "AI Studio mode needs GOOGLE_API_KEY (or GEMINI_API_KEY) — "
                "get one from aistudio.google.com or pass api_key=...",
            )
        logger.info("genai client: AI Studio mode")
        return genai.Client(api_key=key)

    if resolved == "vertex":
        proj = project or (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip() or None
        loc = (
            location
            or (os.environ.get("GOOGLE_CLOUD_LOCATION") or "").strip()
            or DEFAULT_VERTEX_LOCATION
        )
        if not proj:
            raise ValueError(
                "Vertex mode needs GOOGLE_CLOUD_PROJECT (or pass project=...). "
                "Authenticate ADC with `gcloud auth application-default login` first.",
            )
        logger.info("genai client: Vertex mode (project=%s location=%s)", proj, loc)
        return genai.Client(vertexai=True, project=proj, location=loc)

    raise ValueError(f"Unknown genai mode: {resolved!r}")


def has_credentials() -> tuple[bool, GenAIMode | None]:
    """Cheap pre-flight: do we have credentials for ANY mode without raising?"""
    if _vertex_envs_set() and (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip():
        return True, "vertex"
    if _read_api_key():
        return True, "ai_studio"
    return False, None
