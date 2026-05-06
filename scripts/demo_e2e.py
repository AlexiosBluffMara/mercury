#!/usr/bin/env python3
"""demo_e2e.py — exercise every Mercury surface end-to-end + capture assets.

Runs sequentially:
  1. TUI: `mercury -z "..."` -> capture stdout to assets/demo/tui-output.txt
  2. Cortex backend: submit a tiny scan, capture the JSON response
  3. Mercury inference (public): curl the live MTP endpoint
  4. Discord: post a prompt mentioning the bot, wait for response, capture both
  5. Heartbeat snapshot + gaming-mode state at the moment of demo
  6. Patchright screenshots: TUI, Cortex page, Mercury dashboard, Discord-via-API-render

Output: D:/mercury/assets/demo/* (markdown log + json + screenshots).
"""
from __future__ import annotations
import asyncio, json, os, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone

OUT = Path(r"D:/mercury/assets/demo")
OUT.mkdir(parents=True, exist_ok=True)

MERCURY_EXE = r"C:\Users\soumi\AppData\Local\Programs\Python\Python312\Scripts\mercury.exe"
DISCORD_BOT_USER_ID = "1335430089671970837"  # @Snowy The Bot
DISCORD_TEST_CHANNEL = "1501660119350644808"  # bot-test-4

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _log_md(rows: list[tuple[str, str]]) -> None:
    """Append a markdown snapshot of all collected rows to demo.md."""
    p = OUT / "demo.md"
    with p.open("w", encoding="utf-8") as f:
        f.write(f"# Mercury end-to-end demo — {_now()}\n\n")
        for h, body in rows:
            f.write(f"## {h}\n\n")
            f.write(body)
            f.write("\n\n---\n\n")
    print(f"[{_now()}] wrote {p}")


def step_tui() -> tuple[str, str]:
    print(f"[{_now()}] STEP 1: TUI smoke test", flush=True)
    prompt = "In one sentence, why does running Gemma 4 locally on consumer hardware matter for digital equity?"
    try:
        r = subprocess.run(
            [MERCURY_EXE, "-z", prompt],
            capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace",
        )
        out = (r.stdout or "")
        err = (r.stderr or "")
        body = f"### Prompt\n\n```\n{prompt}\n```\n\n### Response\n\n```\n{out.strip() or '(empty)'}\n```\n"
        if err.strip():
            body += f"\n### stderr\n\n```\n{err.strip()[-500:]}\n```\n"
        return ("TUI: `mercury -z`", body)
    except Exception as e:
        return ("TUI: `mercury -z`", f"FAILED: {e}")


def step_public_mtp() -> tuple[str, str]:
    print(f"[{_now()}] STEP 2: Public MTP endpoint", flush=True)
    import urllib.request, urllib.error
    body_data = json.dumps({
        "model": "unsloth/gemma-4-E4B-it-UD-MLX-4bit",
        "messages": [{"role": "user", "content": "Reply with: Mercury MTP live."}],
        "max_tokens": 30,
    }).encode()
    t0 = time.time()
    try:
        req = urllib.request.Request(
            "https://inference.redteamkitchen.com/v1/chat/completions",
            data=body_data, headers={"Content-Type": "application/json", "User-Agent": "mercury-e2e-demo/1.0"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        elapsed = time.time() - t0
        content = data["choices"][0]["message"].get("content", "")
        usage = data.get("usage", {})
        return ("Public MTP at `inference.redteamkitchen.com`",
                f"### Wall time: {elapsed:.2f}s\n\n### Response\n\n```\n{content}\n```\n\n### Usage\n\n```json\n{json.dumps(usage, indent=2)}\n```\n")
    except Exception as e:
        return ("Public MTP", f"FAILED: {e}")


def step_cortex() -> tuple[str, str]:
    print(f"[{_now()}] STEP 3: Cortex backend health", flush=True)
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:8773/api/health", timeout=8) as r:
            data = json.loads(r.read())
        return ("Cortex backend `/api/health`",
                f"```json\n{json.dumps(data, indent=2)}\n```\n")
    except Exception as e:
        return ("Cortex backend", f"FAILED: {e}")


def step_discord() -> tuple[str, str]:
    print(f"[{_now()}] STEP 4: Discord prompt + response", flush=True)
    import urllib.request
    token = ""
    env_path = Path.home() / ".mercury" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DISCORD_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not token:
        return ("Discord", "FAILED: no DISCORD_BOT_TOKEN")

    # Note: posting via the bot's REST API does NOT trigger the gateway —
    # the bot ignores its own messages. We post a "demo header" message via API
    # so the channel has a marker, then snapshot the latest 5 messages
    # (the user can manually trigger a real bot response separately).
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json", "User-Agent": "mercury-e2e-demo/1.0"}
    marker = f"--- E2E DEMO MARKER {_now()} ---"
    try:
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{DISCORD_TEST_CHANNEL}/messages",
            data=json.dumps({"content": marker}).encode(), headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            posted = json.loads(r.read())
        time.sleep(2)
        req2 = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{DISCORD_TEST_CHANNEL}/messages?limit=5",
            headers={"Authorization": f"Bot {token}", "User-Agent": "mercury-e2e-demo/1.0"}, method="GET",
        )
        with urllib.request.urlopen(req2, timeout=10) as r:
            recent = json.loads(r.read())
        rows = ["### Channel: bot-test-4 (`1501660119350644808`)", ""]
        rows.append(f"### Latest 5 messages (newest first):\n")
        for m in recent:
            who = m["author"].get("username", "?")
            is_bot = " [BOT]" if m["author"].get("bot") else ""
            content = m["content"].strip().replace("\n", "\n  ")[:600]
            rows.append(f"- **{who}{is_bot}** @ {m['timestamp'][:19]}\n  ```\n  {content}\n  ```")
        rows.append("")
        return ("Discord (bot-test-4)", "\n".join(rows))
    except Exception as e:
        return ("Discord", f"FAILED: {e}")


def step_infra_snapshot() -> tuple[str, str]:
    print(f"[{_now()}] STEP 5: Infra snapshot (heartbeat + gaming + quota)", flush=True)
    HOME = Path.home() / ".mercury"

    def _read(name: str) -> dict:
        p = HOME / name
        if not p.exists(): return {}
        try: return json.loads(p.read_text())
        except Exception: return {}

    hb = _read("heartbeat_state.json")
    gm = _read("gaming_state.json")
    qt = _read("openrouter_daily_quota.json")
    return ("Infrastructure snapshot",
            f"### Heartbeat\n\n```json\n{json.dumps(hb.get('summary', {}), indent=2)}\n```\n\n"
            f"### Gaming state\n\n```json\n{json.dumps({k: gm.get(k) for k in ['gaming','preferred_provider','running_games','failover_reason']}, indent=2)}\n```\n\n"
            f"### OpenRouter daily quota\n\n```json\n{json.dumps({k: qt.get(k) for k in ['date','free_used','paid_usd']}, indent=2)}\n```\n")


async def step_screenshots() -> tuple[str, str]:
    print(f"[{_now()}] STEP 6: Patchright screenshots", flush=True)
    from patchright.async_api import async_playwright
    targets = [
        ("D1_cortex_demo",         "http://localhost:5173",                            1440,  900),
        ("D2_mercury_dashboard",   "http://localhost:9119",                            1440,  900),
        ("D3_inference_models",    "https://inference.redteamkitchen.com/v1/models",   1200,  600),
        ("D4_cortex_health",       "http://localhost:8773/api/health",                 1200,  600),
        ("D5_mercury_subdomain",   "https://mercury.redteamkitchen.com",               1440,  900),
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                         color_scheme="dark", device_scale_factor=2)
        rows = []
        for stem, url, w, h in targets:
            page = await ctx.new_page()
            await page.set_viewport_size({"width": w, "height": h})
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                await page.evaluate("() => { try { localStorage.clear(); } catch(e) {} }")
                await page.reload(wait_until="domcontentloaded")
                try: await page.wait_for_load_state("networkidle", timeout=5_000)
                except Exception: pass
                await page.wait_for_timeout(1500)
                out = OUT / f"{stem}.png"
                await page.screenshot(path=str(out), full_page=False)
                rows.append(f"- `{out.name}` ({out.stat().st_size//1024} KB) — {url}")
            except Exception as e:
                rows.append(f"- FAILED `{stem}`: {e}")
            finally:
                await page.close()
        await browser.close()
    return ("Demo screenshots", "\n".join(rows))


async def main():
    rows = []
    rows.append(step_tui())
    rows.append(step_public_mtp())
    rows.append(step_cortex())
    rows.append(step_discord())
    rows.append(step_infra_snapshot())
    rows.append(await step_screenshots())
    _log_md(rows)
    print(f"\n[{_now()}] DONE — see {OUT / 'demo.md'} + {OUT}/D*.png")


if __name__ == "__main__":
    asyncio.run(main())
