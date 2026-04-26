"""Google Search Grounding tool for Mercury.

Wraps Gemini's `google_search` built-in tool — when called, the model
silently issues queries to Google Search, retrieves passages, and
returns a grounded answer with citations.  Uses the unified
`google-genai` SDK from `mercury/genai_client.py`, so AI Studio (free
tier) and Vertex AI (paid prod) share one code path.

Pricing as of 2026-04-26 (per
https://ai.google.dev/gemini-api/docs/google-search):

    Gemini 3 models  : 5,000 prompts/month FREE, then $14 per 1k queries
    Gemini 2.5 models: 1,500 requests/day FREE, then $35 per 1k prompts

Each Mercury call counts as ONE prompt; the model may issue multiple
search queries internally per prompt (each billed separately on the
Gemini 3 path).  Mercury defaults to **Gemini 3.1 Flash** — newest Flash variant on
the 3-series with the same $14/1k pricing curve and 5,000 prompts/
month free tier.  Sharper reasoning than 3.0 Flash for the same cost
and quota.  Fallback to gemini-2.5-flash if the 3.1 cap is hit
(2.5 has 1,500/day, $35/1k beyond — ample weekly burst headroom).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.1-flash"

GOOGLE_SEARCH_SCHEMA = {
    "name": "google_search",
    "description": (
        "Answer questions using Google Search via Gemini's grounding feature. "
        "Returns a synthesized answer plus the supporting URLs.  Use this for: "
        "current events, real-time info, factual lookups, '<URL> what is this' "
        "questions where browser_navigate isn't necessary, and anything where "
        "Google's index is the authoritative source.  Free tier covers ~1,500 "
        "calls/day on Gemini 2.5 Flash. Cheaper and faster than browser_navigate "
        "for pure Q&A; use browser_navigate when you need to click through, fill "
        "forms, or extract specific page elements."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The natural-language question to answer.  Phrase it as you "
                    "would to a search engine: 'when did X happen', 'what is Y', "
                    "'how do I Z'.  Pass the user's URL or context in the query "
                    "directly — the model handles URL grounding."
                ),
            },
            "model": {
                "type": "string",
                "description": (
                    "Gemini model id.  Default 'gemini-3.1-flash' (5k/month "
                    "free, $14/1k beyond).  Use 'gemini-2.5-flash' if 3.1 is "
                    "rate-limited (1500/day free) or 'gemini-3.1-pro' for "
                    "harder questions once free has been spent."
                ),
                "default": DEFAULT_MODEL,
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature 0.0-2.0; default 0.4 for factual Q&A.",
                "default": 0.4,
            },
        },
        "required": ["query"],
    },
}


def _format_response(response: Any) -> dict[str, Any]:
    """Extract grounded answer + citations from a genai response."""
    text = getattr(response, "text", "") or ""
    citations: list[dict[str, str]] = []
    queries: list[str] = []

    for cand in getattr(response, "candidates", None) or []:
        gm = getattr(cand, "grounding_metadata", None)
        if gm is None:
            continue
        for q in getattr(gm, "web_search_queries", None) or []:
            if q and q not in queries:
                queries.append(str(q))
        for chunk in getattr(gm, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            if web is None:
                continue
            citations.append({
                "title": getattr(web, "title", "") or "",
                "uri": getattr(web, "uri", "") or "",
            })

    return {
        "ok": True,
        "answer": text,
        "citations": citations,
        "search_queries": queries,
    }


def google_search_tool(
    args: dict | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Run a Google-grounded query through Gemini and return answer + citations."""
    args = args or {}
    query = (args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "missing_query", "message": "query is required"}

    model = (args.get("model") or DEFAULT_MODEL).strip()
    temperature = float(args.get("temperature", 0.4))

    try:
        from google.genai import types as genai_types

        from mercury.genai_client import has_credentials, make_client
    except ImportError as exc:
        return {
            "ok": False,
            "error": "missing_dep",
            "message": f"google-genai not importable: {exc}",
        }

    ok, mode = has_credentials()
    if not ok:
        return {
            "ok": False,
            "error": "no_credentials",
            "message": (
                "Set GEMINI_API_KEY (free tier from aistudio.google.com) or "
                "GOOGLE_CLOUD_PROJECT + ADC for Vertex.  See "
                "mercury/genai_client.py for the resolution order."
            ),
        }

    try:
        client = make_client("auto")
        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
        )
        response = client.models.generate_content(
            model=model,
            contents=query,
            config=config,
        )
    except Exception as exc:
        logger.exception("google_search failed")
        return {
            "ok": False,
            "error": "api_error",
            "message": f"{type(exc).__name__}: {exc}",
            "mode": mode,
        }

    out = _format_response(response)
    out["model"] = model
    out["mode"] = mode
    return out


def _check_google_search_ready() -> bool:
    try:
        from mercury.genai_client import has_credentials
        ok, _ = has_credentials()
        return ok
    except Exception:
        return False


from tools.registry import registry  # noqa: E402

registry.register(
    name="google_search",
    toolset="web",
    schema=GOOGLE_SEARCH_SCHEMA,
    handler=google_search_tool,
    check_fn=_check_google_search_ready,
    requires_env=["GEMINI_API_KEY"],
    is_async=False,
    description=GOOGLE_SEARCH_SCHEMA["description"],
    emoji="🔎",
    max_result_size_chars=8000,
)
