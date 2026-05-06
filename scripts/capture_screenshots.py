#!/usr/bin/env python3
"""capture_screenshots.py — Capture submission validation screenshots.

Uses Patchright (already in the cortex venv) to drive Chromium headlessly,
visit every URL we mention in the submission docs, screenshot it, save to
D:/mercury/assets/screenshots/. Then copy the public-facing ones to
D:/cortex/assets/screenshots/ too.

Run from Windows:
    "C:\\Users\\soumi\\cortex\\.venv\\Scripts\\python.exe" D:\\mercury\\scripts\\capture_screenshots.py
"""
from __future__ import annotations
import asyncio, sys, os
from pathlib import Path

OUT_DIR = Path(r"D:/mercury/assets/screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Public-facing URLs that go in the submission. Each tuple: (filename_stem, url, full_page?)
SHOTS = [
    ("01_mercury_github_repo",        "https://github.com/AlexiosBluffMara/mercury",                                            False),
    ("02_mercury_readme_full",        "https://github.com/AlexiosBluffMara/mercury#readme",                                     True),
    ("03_submission_gemma4",          "https://github.com/AlexiosBluffMara/mercury/blob/main/SUBMISSION_GEMMA4.md",            True),
    ("04_get_started",                "https://github.com/AlexiosBluffMara/mercury/blob/main/GET_STARTED.md",                  True),
    ("05_mercury_cortex_contract",    "https://github.com/AlexiosBluffMara/mercury/blob/main/docs/MERCURY_CORTEX_CONTRACT.md",  True),
    ("06_hackathon_costs",            "https://github.com/AlexiosBluffMara/mercury/blob/main/docs/HACKATHON_COSTS_2026-05-06.md", True),
    ("07_cloud_replication",          "https://github.com/AlexiosBluffMara/mercury/blob/main/docs/CLOUD_REPLICATION_2026-05-06.md", True),
    ("08_gemma4_update",              "https://github.com/AlexiosBluffMara/mercury/blob/main/docs/GEMMA4_UPDATE_2026-05-06.md", True),
    ("09_self_update_loop",           "https://github.com/AlexiosBluffMara/mercury/blob/main/docs/SELF_UPDATE_LOOP_2026-05-06.md", True),
    ("10_submission_readiness",       "https://github.com/AlexiosBluffMara/mercury/blob/main/docs/SUBMISSION_READINESS_2026-05-06.md", True),
    ("11_cortex_github_repo",         "https://github.com/AlexiosBluffMara/cortex",                                             False),
    ("12_cortex_live_demo",           "https://cortex.redteamkitchen.com",                                                      False),
    ("13_cortex_gallery",             "https://cortex.redteamkitchen.com/gallery.html",                                         False),
    ("14_cortex_personas",            "https://cortex.redteamkitchen.com/personas.html",                                        False),
    ("15_kaggle_hackathon",           "https://www.kaggle.com/competitions/gemma-4-good-hackathon",                             False),
    ("16_unsloth_e4b_card",           "https://huggingface.co/unsloth/gemma-4-E4B-it-UD-MLX-4bit",                              False),
    ("17_google_drafter_card",        "https://huggingface.co/google/gemma-4-E4B-it-assistant",                                 False),
]

async def main():
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--window-size=1440,900"])
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                         color_scheme="dark")
        for stem, url, full_page in SHOTS:
            page = await ctx.new_page()
            try:
                print(f"  -> {stem}: {url}", flush=True)
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                # Wait a bit for late-loading assets
                try:
                    await page.wait_for_load_state("networkidle", timeout=8_000)
                except Exception:
                    pass
                await page.wait_for_timeout(1500)
                out = OUT_DIR / f"{stem}.png"
                await page.screenshot(path=str(out), full_page=full_page)
                size_kb = out.stat().st_size // 1024
                print(f"     {size_kb} KB -> {out.name}", flush=True)
            except Exception as e:
                print(f"     FAILED ({e})", flush=True)
            finally:
                await page.close()
        await browser.close()
    print("\nDone. Output:")
    for f in sorted(OUT_DIR.glob("*.png")):
        print(f"  {f.stat().st_size//1024:>5} KB  {f.name}")

if __name__ == "__main__":
    asyncio.run(main())
