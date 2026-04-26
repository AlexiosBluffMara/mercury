"""End-to-end smoke test for Mercury's tool stack.

Hits every API that can be tested without a TTY / browser flow and
prints a single PASS/FAIL line per check.  Intended to run after
`scripts/gcloud_bootstrap.sh` to verify each tool actually responds.

Usage:
    "C:/Users/soumi/mercury/.venv/Scripts/python.exe" "D:/mercury/scripts/e2e_smoke.py"
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path


def _load_env(path: str = "C:/Users/soumi/.mercury/.env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()

# Make sure tools/ + mercury/ are importable
sys.path.insert(0, "D:/mercury")

results: list[tuple[str, str, str]] = []

def record(name: str, ok: bool, info: str) -> None:
    status = "PASS" if ok else "FAIL"
    results.append((name, status, info))
    print(f"  [{status}] {name:35s} {info}")


def safe(label: str, fn):
    print(f"==> {label}")
    try:
        fn()
    except Exception as exc:
        record(label, False, f"{type(exc).__name__}: {str(exc)[:200]}")
        if os.environ.get("E2E_VERBOSE"):
            traceback.print_exc()


# ─── Mercury core / Cortex bridge ───────────────────────────────────────────

def t_cortex_bridge():
    from mercury import cortex_bridge
    state = cortex_bridge.cortex_state()
    vram = cortex_bridge.cortex_vram_report()
    if state in {"idle", "gemma_active", "tribe_active", "swapping"} and vram.get("available"):
        record("cortex_bridge", True, f"state={state} free_gb={vram.get('free_gb')}")
    else:
        record("cortex_bridge", False, f"state={state}")


def t_genai_creds():
    from mercury.genai_client import has_credentials, detect_mode
    ok, mode = has_credentials()
    record("genai credentials", ok, f"mode={mode}")


# ─── Tool registry ──────────────────────────────────────────────────────────

def t_tool_registry():
    from tools.registry import discover_builtin_tools, registry
    discover_builtin_tools()
    n = len(registry._snapshot_entries())
    record("tool registry", n >= 65, f"{n} tools registered")


# ─── Gemini Search Grounding ────────────────────────────────────────────────

def t_google_search():
    from tools.google_search import google_search_tool
    res = google_search_tool({"query": "What is the official Illinois State University mascot?"})
    if res.get("ok"):
        ans = (res.get("answer") or "")[:80].replace("\n", " ")
        cites = len(res.get("citations") or [])
        record("google_search (Gemini 3.1 grounding)", True, f"answer='{ans}...' citations={cites}")
    else:
        record("google_search (Gemini 3.1 grounding)", False, f"{res.get('error')}: {res.get('message','')[:120]}")


# ─── Books API ──────────────────────────────────────────────────────────────

def t_books():
    from tools.google_services import google_books_search
    res = google_books_search({"isbn": "9780262035613"})  # Goodfellow Deep Learning
    if res.get("ok"):
        n = len(res.get("results") or [])
        first = (res.get("results") or [{}])[0]
        record("books API", n > 0, f"{n} results, first: {first.get('title','?')[:50]}")
    else:
        record("books API", False, f"{res.get('error')}: {res.get('message','')[:120]}")


# ─── Knowledge Graph ────────────────────────────────────────────────────────

def t_kg():
    from tools.google_services import google_knowledge_graph
    res = google_knowledge_graph({"query": "Illinois State University", "limit": 3})
    if res.get("ok"):
        n = len(res.get("entities") or [])
        first = (res.get("entities") or [{}])[0]
        record("knowledge graph", n > 0, f"{n} entities, top: {first.get('name','?')[:50]}")
    else:
        record("knowledge graph", False, f"{res.get('error')}: {res.get('message','')[:120]}")


# ─── Translate ──────────────────────────────────────────────────────────────

def t_translate():
    from tools.google_services import google_translate
    res = google_translate({"text": "Hello, world. Mercury is online.", "target_lang": "ja"})
    if res.get("ok"):
        out = (res.get("translations") or [{}])[0].get("translated", "")
        record("translate v3", True, f"ja: {out[:60]}")
    else:
        record("translate v3", False, f"{res.get('error')}: {res.get('message','')[:120]}")


# ─── Maps Routes + Places ───────────────────────────────────────────────────

def t_maps_directions():
    from tools.google_services import google_maps_directions
    res = google_maps_directions({
        "origin": "Illinois State University, Normal, IL",
        "destination": "State Farm Center, Champaign, IL",
        "mode": "DRIVE",
    })
    if res.get("ok") and res.get("routes"):
        r = res["routes"][0]
        record("maps routes", True, f"distance_m={r.get('distanceMeters')} duration={r.get('duration')}")
    else:
        record("maps routes", False, f"{res.get('error')}: {res.get('message','')[:160]}")


def t_maps_along_route():
    from tools.google_services import google_maps_find_along_route
    res = google_maps_find_along_route({
        "origin": "Illinois State University, Normal, IL",
        "destination": "State Farm Center, Champaign, IL",
        "query": "coffee shop",
        "max_detour_minutes": 5,
    })
    if res.get("ok"):
        n = len(res.get("places") or [])
        first = (res.get("places") or [{}])[0]
        name = (first.get("displayName") or {}).get("text", "?")
        record("maps places along-route", n > 0, f"{n} places, top: {name[:50]}")
    else:
        record("maps places along-route", False, f"{res.get('error')}: {res.get('message','')[:160]}")


# ─── TTS ────────────────────────────────────────────────────────────────────

def t_tts():
    from tools.google_services import google_text_to_speech
    out_path = "D:/mercury/.cache/tts_smoke.mp3"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    res = google_text_to_speech({
        "text": "Mercury smoke test successful.",
        "voice_name": "en-US-Neural2-J",
        "output_path": out_path,
    })
    if res.get("ok"):
        sz = Path(out_path).stat().st_size
        record("text-to-speech (Neural2)", True, f"wrote {sz} bytes to {out_path}")
    else:
        record("text-to-speech (Neural2)", False, f"{res.get('error')}: {res.get('message','')[:160]}")


# ─── Vision ─────────────────────────────────────────────────────────────────

def t_vision():
    from tools.google_services import google_vision_ocr
    # use a known public image with text — Wikipedia signpost
    res = google_vision_ocr({"image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/VAN_CAT.png/240px-VAN_CAT.png"})
    if res.get("ok"):
        n_labels = len(res.get("labels") or [])
        record("cloud vision (labels+OCR)", True, f"{n_labels} labels detected")
    else:
        record("cloud vision (labels+OCR)", False, f"{res.get('error')}: {res.get('message','')[:160]}")


# ─── Firecrawl ──────────────────────────────────────────────────────────────

def t_firecrawl():
    from tools.firecrawl_tool import firecrawl_tool
    res = firecrawl_tool({"url": "https://example.com"})
    if res.get("ok"):
        md = (res.get("markdown") or "")[:60].replace("\n", " ")
        record("firecrawl scrape", True, f"title='{res.get('title')}' md='{md}...'")
    else:
        record("firecrawl scrape", False, f"{res.get('error')}: {res.get('message','')[:160]}")


# ─── Run ────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("Mercury end-to-end smoke test")
    print("=" * 70)
    safe("cortex_bridge",         t_cortex_bridge)
    safe("genai credentials",     t_genai_creds)
    safe("tool registry",         t_tool_registry)
    safe("google_search",         t_google_search)
    safe("books API",             t_books)
    safe("knowledge graph",       t_kg)
    safe("translate v3",          t_translate)
    safe("maps routes",           t_maps_directions)
    safe("maps places along-route", t_maps_along_route)
    safe("text-to-speech",        t_tts)
    safe("vision",                t_vision)
    safe("firecrawl",             t_firecrawl)
    print()
    print("=" * 70)
    n_pass = sum(1 for _, s, _ in results if s == "PASS")
    n_fail = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"Result: {n_pass} pass / {n_fail} fail / {time.time()-t0:.1f}s wall")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
