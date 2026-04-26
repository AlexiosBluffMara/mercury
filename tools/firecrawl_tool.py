"""Firecrawl tool for Mercury.

Firecrawl turns any URL into clean LLM-ready markdown — handles
JS-rendered pages, paywalls (where allowed), and PDF extraction.
Complements the google_search + agent-browser stack: use this when
you want the *raw markdown* of a single URL the user pasted, not a
synthesized search answer.

Pricing (firecrawl.dev):
  Free tier: 500 page-scrapes/month, 5 concurrent
  Paid: $19/mo for 3k scrapes, $99/mo for 100k scrapes

Setup:
  1. Sign up at firecrawl.dev with a Google account
  2. Get the API key from dashboard
  3. Add to ~/.hermes/.env: FIRECRAWL_API_KEY=fc-...
  4. Mercury picks it up automatically — no restart needed for new turns
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.firecrawl.dev/v1"

FIRECRAWL_SCHEMA = {
    "name": "firecrawl_scrape",
    "description": (
        "Fetch a single URL and return its content as clean Markdown.  Handles "
        "JS-rendered pages, removes nav/ads/footers, extracts main content.  "
        "Use for: PDF/article extraction, getting clean text from a paywall-"
        "soft URL, scraping for further analysis.  Prefer google_search for "
        "open-ended questions; use this when the user gives you a specific URL "
        "and wants its full content.  Free tier: 500 scrapes/month."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to scrape"},
            "only_main_content": {
                "type": "boolean",
                "description": "Strip nav/footer/ads (default true).  Disable to get full HTML structure.",
                "default": True,
            },
            "formats": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Output formats. Default ['markdown'].  Options: markdown, html, links, screenshot.",
                "default": ["markdown"],
            },
            "wait_for_ms": {
                "type": "integer",
                "description": "Milliseconds to wait for JS to settle before extracting (default 2000).",
                "default": 2000,
            },
        },
        "required": ["url"],
    },
}


def firecrawl_tool(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    url = (args.get("url") or "").strip()
    if not url:
        return {"ok": False, "error": "missing_url", "message": "url is required"}

    api_key = (os.environ.get("FIRECRAWL_API_KEY") or "").strip()
    if not api_key:
        return {
            "ok": False,
            "error": "no_credentials",
            "message": (
                "Set FIRECRAWL_API_KEY in ~/.hermes/.env.  Free tier at "
                "firecrawl.dev gives 500 scrapes/month."
            ),
        }

    base_url = os.environ.get("FIRECRAWL_API_URL", DEFAULT_BASE_URL).rstrip("/")

    import httpx

    payload = {
        "url": url,
        "onlyMainContent": bool(args.get("only_main_content", True)),
        "formats": args.get("formats") or ["markdown"],
        "waitFor": int(args.get("wait_for_ms", 2000)),
    }

    try:
        resp = httpx.post(
            f"{base_url}/scrape",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPStatusError as exc:
        try:
            err = exc.response.json()
        except Exception:
            err = {"text": exc.response.text[:500]}
        return {
            "ok": False,
            "error": "http_error",
            "message": f"HTTP {exc.response.status_code}: {err}",
        }
    except Exception as exc:
        logger.exception("firecrawl_tool failed")
        return {"ok": False, "error": "request_error", "message": str(exc)}

    if not body.get("success"):
        return {"ok": False, "error": "firecrawl_error", "message": body.get("error", "unknown")}

    data = body.get("data") or {}
    return {
        "ok": True,
        "url": url,
        "markdown": (data.get("markdown") or "")[:80000],
        "title": (data.get("metadata") or {}).get("title", ""),
        "description": (data.get("metadata") or {}).get("description", ""),
        "links": data.get("links") or [],
        "screenshot": data.get("screenshot"),
    }


def _check_firecrawl_ready() -> bool:
    return bool((os.environ.get("FIRECRAWL_API_KEY") or "").strip())


from tools.registry import registry  # noqa: E402

registry.register(
    name="firecrawl_scrape",
    toolset="web",
    schema=FIRECRAWL_SCHEMA,
    handler=firecrawl_tool,
    check_fn=_check_firecrawl_ready,
    requires_env=["FIRECRAWL_API_KEY"],
    is_async=False,
    description=FIRECRAWL_SCHEMA["description"],
    emoji="🔥",
    max_result_size_chars=80000,
)
