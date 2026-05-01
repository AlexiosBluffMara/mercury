# External-trigger safety — rate limits, daily caps, kill switch

When Mercury is exposed publicly (Discord bot in shared servers, web
endpoint at `mercury.redteamkitchen.com`), every external request is
gated by `gateway/external_limits.py` and logged by
`gateway/external_logging.py`.

This is **additive** — terminal chat, owner-DMs, and any request from
an allowlisted operator bypass the limits.

## Config schema — `~/.mercury/config.yaml`

```yaml
external_limits:
  # Hard kill switch. When true, the gateway refuses every external
  # request with the polite "I'm offline" message until you flip it
  # back. /kill (Discord, owner-only) and the kill-switch endpoint set
  # this at runtime; the value is then persisted here.
  enabled: true

  # Per-IP rate limits for the public web endpoint.
  web:
    per_minute: 5
    per_hour: 30
    # Anything in this CIDR list is exempt from rate limits.
    allowlist_cidrs:
      - "127.0.0.1/32"

  # Per-user rate limits for Discord (anonymous, non-allowlisted users).
  discord:
    per_minute: 5
    per_hour: 30

  # Allowlist of Discord user IDs that get the operator-tier limits
  # (effectively unlimited). Owner IDs from DISCORD_OWNER_IDS are
  # automatically included.
  operators_discord:
    - "123456789012345678"   # Soumit
    # add collaborators here

  # Hard cap across ALL external surfaces per UTC day. After this many
  # successful inferences, every new external request gets the daily-cap
  # reply. Reset at 00:00 UTC.
  daily_cap: 1000

  # Polite reply when the daily cap is hit.
  daily_cap_message: "I've hit my daily limit — back tomorrow."

  # Polite reply when the kill switch is engaged.
  kill_switch_message: >-
    Snowy is paused for maintenance.  External requests are off until
    the operator flips them back on.  (The owner is still able to use
    the local terminal and DM channels.)

  # Optional: where to POST a "Snowy back online" message on gateway
  # startup. Leave empty to disable.
  status_webhook_url: ""
```

If the file or section is missing, the defaults above apply.

## Behavior

1. **Request comes in** (`/api/chat` from web, or a Discord message that
   isn't from the owner / DM).
2. `external_limits.check(surface, identity)` runs:
   - If `enabled` is false → 503 / kill-switch reply.
   - If daily counter ≥ `daily_cap` → daily-cap reply.
   - If identity is in the relevant allowlist → pass through.
   - Else evaluate the per-minute / per-hour budget; if exceeded → 429
     / "easy there, try again in N seconds".
3. The request is logged to
   `~/.mercury/logs/external/YYYY-MM-DD.jsonl`:
   ```json
   {"ts":"2026-05-01T12:34:56Z","surface":"discord","user":"123…",
    "prompt_prefix":"how do I…","latency_ms":1240,"model":"gemma3:27b",
    "outcome":"ok"}
   ```
4. On gateway startup, if `status_webhook_url` is set, Mercury POSTs
   `{"content":"Snowy back online — running on Soumit's 5090 in
   Chicago"}` to it.

## Runtime controls

- **Discord (owner-only)**: `/kill` toggles `external_limits.enabled`.
  Reply is ephemeral. Identity is matched against
  `DISCORD_OWNER_IDS`.
- **HTTP**: `POST /api/external-limits/kill` with header
  `X-Mercury-Owner: <secret>`. The secret is `MERCURY_OWNER_SECRET` from
  the env. Returns the new state.
- **Status**: `GET /api/health` returns
  `{"status":"online","external_enabled":true,"daily_used":42,
  "daily_cap":1000,"vram_free_gb":18.4}`.

## Why this exists

The whole point of Mercury is that it lives on the operator's hardware.
The moment it's reachable from the open internet, two new failure modes
appear: someone abuses the inference endpoint (cost / GPU heat / queue
starvation for the operator's own jobs), or someone tries to use the
bot as a passthrough to the operator's local files / shell. The kill
switch is the *one-flip* containment plan; the daily cap and per-IP
budget are the *quiet steady-state* containment.

If you ever see weird traffic in
`~/.mercury/logs/external/<date>.jsonl`, hit `/kill` first and triage
second.
