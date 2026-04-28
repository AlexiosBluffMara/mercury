---
name: discord-bot
description: Drive Mercury's brain-pipeline via a Discord bot. Use when the user wants to drop a video into a Discord channel and get a 3D cortical activation map plus three-tier narration as a reply, or any other "agent-as-bot" Discord workflow. Composes Mercury's existing gateway/discord with brain-viz / fmri-overlay / cortex-bridge.
version: 0.1.0
author: Mercury
license: MIT
metadata:
  hermes:
    tags: [discord, bot, gateway, brain-viz, neuroscience, demo]
    category: platforms
    related_skills: [brain-viz, fmri-overlay, cortex-bridge, tailnet]
prerequisites:
  files: [D:/mercury/gateway/discord]
  env:
    - DISCORD_BOT_TOKEN
    - DISCORD_GUILD_ID         # optional — restrict slash commands to one guild
  python_packages: [cortex, "discord.py>=2.5"]
---

# Discord Bot — Brain Pipeline as Slash Commands

Mercury already has a generic Discord gateway in `gateway/discord/`. This
skill is the **knowledge document** for using that gateway specifically for
the brain-response pipeline (the Jemma flow from `D:/TRIBEV2/bot/`).

The TRIBEV2 standalone bot will be retired in favor of Mercury's gateway —
one process serves all platforms (Discord, WhatsApp, Telegram, Slack, etc.)
instead of a separate bot per surface. This skill documents the user-facing
slash commands the agent should expose.

## When to Use

- User says "make a Discord bot that..." — first reach for Mercury's
  gateway, not a new bot
- User asks "can I drop a video in Discord and get the brain scan back?"
- User asks "how do I demo Jemma over Discord?" — yes, that's now Mercury
- User wants a slash command for any composed brain-pipeline flow

**Do NOT use** to build a *generic* Discord bot — that's just Mercury's
gateway. This skill is specifically the brain-pipeline / hackathon flow.

## Slash Commands Exposed

| Command | Args | What it does |
|---|---|---|
| `/brain` | `<attachment: video/audio>` | Full pipeline: media_gate → brain_scan → narrate → reply with 3D viewer URL + toddler-tier narration in chat. **The marquee command.** |
| `/scan` | `<attachment>` | Same as `/brain` but no narration — fastest path to the visual |
| `/explain` | `<scan_id>` `<tier>` | Re-narrate an existing scan at a different tier (`toddler` / `clinician` / `researcher`) |
| `/cortex-state` | — | Returns current GPU state from `cortex_bridge.cortex_state()` — useful for queue debugging |
| `/recent` | — | Lists the user's last 5 scans with viewer URLs (per-user via `Tailscale-User-Login` derived from Discord user ID) |

All commands are gated on:
1. The user having posted in the configured guild (`DISCORD_GUILD_ID`)
2. Cortex being reachable (`cortex_state() != "unavailable"`)
3. The attachment being ≤ 50 seconds (per TRIBE v2's `duration_trs` lock)

## How It Works

```
                Discord user posts /brain + attachment
                            │
                            ▼
            Mercury gateway (gateway/discord) receives the slash command
                            │
                            ▼ tool call
                       brain-viz skill
                            │ ↓ calls
                ┌───────────┼─────────────┐
                ▼           ▼             ▼
       cortex-bridge     three-js-      cortex-bridge
       .media_gate       component      .narrate
       .brain_scan        (existing      (×3 tiers)
                          webapp URL)
                            │
                            ▼
            Mercury gateway formats reply:
              • Embed with viewer URL
              • Toddler-tier text in chat
              • Buttons: "Clinician" / "Researcher" → /explain
                            │
                            ▼
                Discord user clicks viewer → opens
                https://brain.redteamkitchen.com/scan/abc123
                (Cloudflare-Tunnel-routed back to RTX 5090)
```

## Step-by-Step Setup

### Step 1 — Configure the gateway

```yaml
# ~/.mercury/config.yaml
gateways:
  discord:
    bot_token_env: DISCORD_BOT_TOKEN
    guild_ids:    ["1234567890"]                  # optional restriction
    skills:       ["brain-viz", "fmri-overlay"]   # which skills the bot exposes
```

### Step 2 — Start the gateway

```bash
mercury gateway up discord
# or as a long-running daemon
mercury gateway run --background discord
```

### Step 3 — Slash-command registration

The first time the bot connects, it auto-syncs slash commands to the
configured guild (instant) or globally (~1 hour propagation).

### Step 4 — User flow (from the user's POV)

1. User joins the configured Discord guild
2. User types `/brain` and attaches a 20-second clip
3. Bot replies with **"Scanning… (this takes 4–7 min)"** and a progress
   indicator (the gateway updates the message via `interaction.followup.edit`)
4. On completion, the message is edited to include:
   - The viewer URL
   - Toddler-tier narration (≤50 words, in the chat directly)
   - Two buttons: "Clinician detail" and "Researcher detail"

## Migration from `D:/TRIBEV2/bot/`

The old standalone Jemma Discord bot (`D:/TRIBEV2/bot/bot.py`) had its own
RBAC, rate-limiting, and analysis-thread features. Migration map:

| TRIBEV2/bot/ thing | Where it lives now |
|---|---|
| `bot.py` (Discord client) | `gateway/discord/` (Mercury's existing gateway) |
| `cat_gate.py` (content gate) | `cortex.media_gate.py` (called via `cortex-bridge.media_gate`) |
| `gemma.py` (narration) | `cortex-bridge.narrate` |
| `pipeline.py` (TRIBE inference) | `cortex.gpu_scheduler` + `cortex_bridge.brain_scan` |
| RBAC | Mercury's `Tailscale-User-Login` identity middleware (Discord user → Mercury identity via `pairing` skill) |
| Rate-limiting | `mercury cron` schedules + per-user request queue (built-in) |
| Analysis threads | Discord's native threads — gateway creates one per `/brain` invocation |

The retired bot stays in `D:/TRIBEV2/bot/` as reference until the migration
ships. **Do not run both bots against the same Discord token** — they'll
fight for slash-command registration.

## Hackathon Submission Notes (Nous Creative 2026)

For the demo recording, Discord is the *delivery surface* of choice:

1. The judge's POV is "user-friendly" — Discord is universally familiar,
   slash commands are obvious, the bot's reply showcases the multi-modal
   output beautifully
2. The recording captures the *agent doing things across surfaces* — the
   slash-command flow shows Hermes Agent's gateway discipline (one process,
   many platforms)
3. **Kimi K2.6** does the planning step inside the gateway (visible in the
   bot's typing indicator: "thinking with kimi-k2.6…") — qualifies for the
   Kimi Track $5K bonus

Trademark line: "Gemma is a trademark of Google LLC." — include in the
bot's `/about` slash-command reply.
