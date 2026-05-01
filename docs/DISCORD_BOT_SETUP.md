# Discord Bot Setup — Snowy The Bot

End-to-end walkthrough for getting **Snowy The Bot** (Mercury's Discord
front door) on a server. Follow this once after generating a fresh token
or whenever the existing token has been revoked.

The bot is the public-facing voice of Mercury — it runs on Soumit's
RTX 5090 in Chicago as part of the **Alexios Bluff Mara × Illinois State
University** research collaboration, and it greets visitors in shared
servers exactly the way Mercury greets the operator in the terminal.

---

## 1. Create / reset the bot in the Discord developer portal

1. Open <https://discord.com/developers/applications> and sign in with the
   account that owns Snowy The Bot.

2. If the app **does not exist**: click **New Application** in the upper
   right, name it `Snowy The Bot`, accept the developer terms, and click
   **Create**. If it already exists, click into it instead.

3. In the left rail click **Bot**.
   - If a bot user has not been created yet, click **Add Bot** → **Yes,
     do it!**.
   - Click **Reset Token** (red button under the bot name). Discord will
     prompt you twice; confirm both times. **Copy the token to a scratch
     buffer — Discord only shows it once.** If you lose it, reset again.

4. Still on the **Bot** page, scroll down to **Privileged Gateway Intents**
   and enable the toggle for **Message Content Intent**. Snowy needs this
   to read non-mention messages in threads and to handle attachments.
   Leave **Server Members Intent** and **Presence Intent** off — Snowy
   does not need them.

5. Save changes (the button appears at the bottom after any toggle).

## 2. Generate the invite URL

1. In the left rail click **OAuth2 → URL Generator**.

2. Under **Scopes**, check:
   - `bot`
   - `applications.commands`

3. A **Bot Permissions** section will appear. Check:
   - `Send Messages`
   - `Read Message History`
   - `Use Slash Commands`
   - `Attach Files`
   - `Embed Links` (recommended — slash command output looks cleaner)
   - `Add Reactions` (recommended — Snowy uses reactions for status)

   Leave everything else off. The default Snowy is read-only outside of
   the messages it generates; do not grant administrator or moderation
   perms.

4. Copy the generated URL at the bottom of the page.

5. Paste the URL into a browser, choose the target server (e.g.
   `#bot-test-3`), and click **Authorize**. Solve the captcha.

   You should see Snowy The Bot appear in the server's member list. It
   will be offline until step 4.

## 3. Wire the token into Mercury's environment

Mercury reads the token from the env var **`DISCORD_BOT_TOKEN`** (Hermes
fork convention; see `mercury_cli/config.py` and `gateway/config.py`).

Two equivalent ways to set it:

**Option A — `~/.hermes/.env` (preferred, this is what `mercury gateway`
loads automatically):**

```bash
# In a fresh git-bash shell:
echo 'DISCORD_BOT_TOKEN=PASTE_THE_TOKEN_HERE' >> ~/.hermes/.env
```

**Option B — set in the current shell only (transient):**

```bash
export DISCORD_BOT_TOKEN=PASTE_THE_TOKEN_HERE
```

Verify the file looks right (token line should be the last line, no
quotes around the value):

```bash
tail -3 ~/.hermes/.env
```

> **Never commit the token.** `~/.hermes/.env` is outside the repo. If
> you ever leak a token, return to step 1 and reset.

## 4. Start the gateway and watch the bot connect

```bash
cd /d/mercury
mercury gateway run -v
```

In the log output you should see, within 5–15 seconds:

```
[discord] Connecting to Discord gateway...
[discord] Logged in as Snowy The Bot#1234 (id=...)
[discord] Synced N slash command(s) via bulk tree sync
```

The bot's status indicator in Discord will turn green.

## 5. Smoke test

In `#bot-test-3`:

- Mention the bot: `@Snowy The Bot hi`. It should reply within a few
  seconds.
- Try a slash command: type `/` and you should see Mercury's commands
  pop up. Run `/status` to confirm the runtime is wired through.
- Slash commands sometimes take **up to an hour** to propagate the
  *first* time after a fresh token. If `/` shows an empty list, wait,
  refresh Discord (`Ctrl+R`), and try again.

## 6. Logs to check if something is wrong

```bash
# Recent bot connection attempts (also includes Telegram/WhatsApp etc.):
tail -200 ~/.mercury/logs/gateway.log

# External-surface request log (one line per Discord/web request):
ls -la ~/.mercury/logs/external/
tail ~/.mercury/logs/external/$(date +%Y-%m-%d).jsonl
```

Common failure modes:

| Symptom | Cause | Fix |
| --- | --- | --- |
| `LoginFailure: Improper token has been passed` | Token typo, stray whitespace, or wrong env file | Re-copy from the developer portal; check `~/.hermes/.env` has no trailing spaces |
| Bot shows online but ignores messages | Message Content Intent off | Step 1.4 — enable, save, restart `mercury gateway run` |
| Slash commands never appear | First-sync propagation delay | Wait 5–60 minutes; refresh client |
| `403 Forbidden` on send | Missing channel permission | Re-generate invite URL with the perms in step 2.3 |

## 7. Owner ID — required for `/kill` and other gated commands

Find your Discord user ID:

1. Discord → User Settings → Advanced → enable **Developer Mode**.
2. Right-click your username anywhere → **Copy User ID**.
3. Add to `~/.hermes/.env`:

```
DISCORD_OWNER_IDS=123456789012345678
```

Multiple owners can be separated by commas. Only IDs in this list can
run `/kill` (the external-traffic kill switch — see
`docs/EXTERNAL_LIMITS.md`).

---

## What's set up after this

- Snowy The Bot is in the target server, online, responding to mentions
  and slash commands.
- Mercury gateway logs every external Discord request to
  `~/.mercury/logs/external/YYYY-MM-DD.jsonl`.
- Slash commands available out of the box (full list via `/help`):
  - `/ask <prompt>` — fast immediate-mode answer
  - `/think <prompt>` — slower deeper reasoning
  - `/scan <attachment>` — submit to Cortex, returns brain-viz URL
  - `/status` — GPU state, free VRAM, queue depth
  - `/skill <name>` — run any Mercury skill (autocompleted)
  - `/help` — full command list + project blurb
  - `/kill` — owner-only external-traffic kill switch

You should not need to repeat this setup unless the token is rotated or
the bot is removed from a server.
