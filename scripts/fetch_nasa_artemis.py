#!/usr/bin/env python3
"""Pull a public-domain NASA Artemis clip and prepare it for the Cortex demo.

NASA imagery and video produced by US federal employees in their official
capacity is not subject to copyright (17 U.S.C. § 105) and is explicitly
released for reuse per NASA's media usage guidelines:
  https://www.nasa.gov/multimedia/guidelines/index.html

This script:
  1. Hits images.nasa.gov's search API for "artemis"
  2. Sorts hits by date (newest first), filters for mission-vehicle visuals
  3. Pulls the smallest-acceptable .mp4 asset for each candidate
  4. Trims a 15-second silent excerpt for the brain-scan demo

Output:
  D:/cortex/assets/nasa_artemis_15s_silent.mp4  (recommended demo input)
  D:/mercury/demo/nasa_source/                  (raw downloads)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _safe_url(url: str) -> str:
    """NASA's asset manifest sometimes contains spaces and other unencoded
    chars in the path. Re-quote the path component safely."""
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(parts.path, safe="/%")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))

API     = "https://images-api.nasa.gov/search"
QUERY   = "artemis"
WANT_KW = ("artemis i", "artemis ii", "artemis 1", "sls", "orion", "moon")
SOURCE_DIR = Path("D:/mercury/demo/nasa_source")
OUT_FINAL  = Path("D:/cortex/assets/nasa_artemis_15s_silent.mp4")
TRIM_SECS  = 15

UA = "Mozilla/5.0 (Mercury demo download; +https://github.com/AlexiosBluffMara/mercury)"


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(_safe_url(url), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def http_download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(_safe_url(url), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, dst.open("wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)


def search_artemis() -> list[dict]:
    print(f"[nasa] querying {API}?q={QUERY}&media_type=video")
    data = http_get_json(f"{API}?q={QUERY}&media_type=video")
    items = data.get("collection", {}).get("items", [])
    print(f"[nasa] {len(items)} video items returned")

    scored: list[tuple[float, dict]] = []
    for item in items:
        meta_list = item.get("data", [])
        if not meta_list:
            continue
        meta = meta_list[0]
        title = (meta.get("title") or "").lower()
        desc  = (meta.get("description") or "").lower()
        date  = meta.get("date_created") or ""
        score = sum(2 for kw in WANT_KW if kw in title) + sum(1 for kw in WANT_KW if kw in desc)
        if score == 0:
            continue
        scored.append((score, {**meta, "asset_href": item.get("href"), "_date": date}))

    scored.sort(key=lambda x: (x[0], x[1].get("_date", "")), reverse=True)
    return [m for _, m in scored[:8]]


def asset_mp4_url(asset_index_url: str) -> str | None:
    """The 'href' on a search hit points to a JSON manifest of all files for
    that asset. Pick the smallest .mp4 (usually labelled 'small.mp4' or
    '~smaller.mp4' or '_small.mp4'). Anything > ~100 MB we skip."""
    try:
        files = http_get_json(asset_index_url)
    except (urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        print(f"[nasa] manifest fetch failed: {exc}")
        return None

    # `files` is a list of URL strings
    candidates = [u for u in files if isinstance(u, str) and u.lower().endswith(".mp4")]
    if not candidates:
        return None

    # Prefer "small" / "smaller" variants, then anything 1080p, then first
    def rank(u: str) -> tuple[int, int]:
        u_low = u.lower()
        small = 0 if any(t in u_low for t in ("small", "preview", "mobile")) else 1
        hd    = 0 if any(t in u_low for t in ("1080", "720", "hd")) else 1
        return (small, hd)

    candidates.sort(key=rank)
    return candidates[0]


def download_first_workable(meta_list: list[dict]) -> Path | None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for meta in meta_list:
        nasa_id = meta.get("nasa_id") or "unknown"
        title = meta.get("title") or "untitled"
        date = meta.get("date_created", "")
        href = meta.get("asset_href")
        if not href:
            continue
        print(f"\n[nasa] candidate: {nasa_id}  ({date[:10]})  {title[:80]}")
        mp4_url = asset_mp4_url(href)
        if not mp4_url:
            print("[nasa]   no mp4 asset")
            continue
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", nasa_id)[:60]
        dst = SOURCE_DIR / f"{safe_id}.mp4"
        if dst.exists() and dst.stat().st_size > 1024 * 100:
            print(f"[nasa]   already on disk: {dst}")
            return dst
        try:
            print(f"[nasa]   downloading: {mp4_url}")
            http_download(mp4_url, dst)
            size_mb = dst.stat().st_size / (1024 * 1024)
            print(f"[nasa]   saved {dst}  ({size_mb:.1f} MB)")
            if size_mb < 0.5:
                print("[nasa]   too small, trying next")
                dst.unlink(missing_ok=True)
                continue
            return dst
        except (urllib.error.URLError, OSError) as exc:
            print(f"[nasa]   download failed: {exc}")
            continue
    return None


def trim_silent(src: Path, dst: Path, seconds: int) -> None:
    """Trim and strip audio. Re-encodes to a clean H.264 baseline that
    Cortex's V-JEPA2 frontend will accept without surprises."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-t", str(seconds),
        "-an",
        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(dst),
    ]
    print(f"\n[ffmpeg] {' '.join(cmd[:5])} ... -> {dst}")
    subprocess.run(cmd, check=True, capture_output=True)
    size_mb = dst.stat().st_size / (1024 * 1024)
    print(f"[ffmpeg] wrote {dst}  ({size_mb:.1f} MB)")


def main() -> int:
    candidates = search_artemis()
    if not candidates:
        print("[nasa] no Artemis matches found", file=sys.stderr)
        return 2

    src = download_first_workable(candidates)
    if not src:
        print("[nasa] could not download any candidate", file=sys.stderr)
        return 3

    trim_silent(src, OUT_FINAL, TRIM_SECS)
    print(f"\nDONE. Demo input: {OUT_FINAL}")
    print("Next: drag this file into the WebUI at http://127.0.0.1:8765/")
    print("Attribution line for video / tweet description:")
    print("  Footage: NASA Artemis program, public domain (17 U.S.C. § 105).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
