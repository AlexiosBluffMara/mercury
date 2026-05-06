#!/usr/bin/env python3
"""capture_local_screenshots.py — Screenshots of locally-running Mercury surfaces."""
from __future__ import annotations
import asyncio, sys
from pathlib import Path

# Ensure no cached theme localStorage from prior runs interferes
CLEAR_LOCALSTORAGE_JS = "() => { try { localStorage.clear(); } catch(e) {} }"

OUT_DIR = Path(r"D:/mercury/assets/screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Each tuple: (filename_stem, url, full_page?, viewport_w, viewport_h)
# :5173 is the Cortex webapp (Vite dev). :9119 is the Mercury dashboard (the
# bundled mercury-web served by mercury_cli/web_server.py).
SHOTS = [
    ("18_mercury_webui_desktop",   "http://localhost:9119",                       False, 1440,  900),
    ("19_mercury_webui_mobile",    "http://localhost:9119",                       False,  390,  844),  # iPhone-ish
    ("20_mercury_webui_tablet",    "http://localhost:9119",                       False,  768, 1024),
    ("21_cortex_demo_local",       "http://localhost:5173",                       False, 1440,  900),
]

async def main():
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--window-size=1440,900"])
        for stem, url, full_page, vw, vh in SHOTS:
            ctx = await browser.new_context(viewport={"width": vw, "height": vh},
                                             color_scheme="dark",
                                             device_scale_factor=2)
            page = await ctx.new_page()
            try:
                print(f"  -> {stem}: {url} ({vw}x{vh})", flush=True)
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                # Clear any cached theme so the page renders the new default
                await page.evaluate(CLEAR_LOCALSTORAGE_JS)
                await page.reload(wait_until="domcontentloaded")
                try:
                    await page.wait_for_load_state("networkidle", timeout=6_000)
                except Exception:
                    pass
                await page.wait_for_timeout(2000)
                out = OUT_DIR / f"{stem}.png"
                await page.screenshot(path=str(out), full_page=full_page)
                print(f"     {out.stat().st_size//1024} KB -> {out.name}", flush=True)
            except Exception as e:
                print(f"     FAILED: {e}", flush=True)
            finally:
                await page.close()
                await ctx.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
