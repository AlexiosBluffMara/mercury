#!/usr/bin/env python3
"""capture_public_subdomains.py — screenshot the live redteamkitchen.com subdomains."""
from __future__ import annotations
import asyncio
from pathlib import Path

OUT_DIR = Path(r"D:/mercury/assets/screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SHOTS = [
    ("22_inference_subdomain",    "https://inference.redteamkitchen.com/v1/models",     False),
    ("23_mercury_subdomain",      "https://mercury.redteamkitchen.com",                 False),
    ("24_ollama_subdomain",       "https://ollama.redteamkitchen.com/api/tags",         False),
    ("25_cortex_subdomain_fresh", "https://cortex.redteamkitchen.com",                  False),
]

async def main():
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                         color_scheme="dark")
        for stem, url, full in SHOTS:
            page = await ctx.new_page()
            try:
                print(f"  -> {stem}: {url}", flush=True)
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                try: await page.wait_for_load_state("networkidle", timeout=5_000)
                except Exception: pass
                await page.wait_for_timeout(1500)
                out = OUT_DIR / f"{stem}.png"
                await page.screenshot(path=str(out), full_page=full)
                print(f"     {out.stat().st_size//1024} KB", flush=True)
            except Exception as e:
                print(f"     FAILED: {e}", flush=True)
            finally:
                await page.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
