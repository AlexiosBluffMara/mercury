# RTK operations runbook

How the Red Team Kitchen × ISU stack stays up on the 5090, and what to do
when something breaks.

## The picture

```
                   internet
                      │
                      ▼
            ┌────────────────────┐
            │ Cloudflare edge    │  mercury.redteamkitchen.com
            │                    │  ollama.redteamkitchen.com
            └─────────┬──────────┘
                      │ (cloudflared tunnel: rtk-5090)
                      ▼
   ┌──────────────────────────────────────────────────┐
   │   RTX 5090 desktop (Windows 11 Pro, Chicago)     │
   │                                                  │
   │  ┌─────────────────┐  ┌────────────────────┐    │
   │  │ rtk-cloudflared │  │ rtk-cortex-webapp  │    │
   │  │ (NSSM service)  │  │ uvicorn :8765      │    │
   │  └─────────────────┘  └────────────────────┘    │
   │  ┌────────────────────────────────────────┐     │
   │  │ rtk-mercury-gateway                    │     │
   │  │ Hermes-fork agent + Discord bot        │     │
   │  └────────────────────────────────────────┘     │
   │                  ▲                              │
   │                  │ probes every 60s             │
   │  ┌───────────────┴──────────────┐               │
   │  │ rtk-health-monitor (Task     │               │
   │  │ Scheduler) — restarts on     │               │
   │  │ failure, alerts Discord      │  ─── webhook ─► #alerts
   │  └──────────────────────────────┘               │
   └──────────────────────────────────────────────────┘
```

## Operator entry points

After installation the operator has four ways to drive the stack:

1. **PowerShell installer** — `D:\mercury\scripts\windows-services\install-services.ps1`. Self-elevating, idempotent, downloads NSSM if missing, registers all three services. **This is the only command needed to make the stack self-managing on Windows.**
2. **Local TUI** — `python -m rtk_tui` from `D:\mercury\scripts\`. Live status / hotkey restart / log tail / inline test prompt. Works over SSH.
3. **Discord** — `/services list`, `/services restart <name>`, `/services logs <name>`. Owner-gated by `DISCORD_OWNER_IDS`. Use this when the operator is on the phone and away from the desktop.
4. **Health monitor** — `D:\mercury\scripts\health-monitor\monitor.py`, registered with Task Scheduler via `install-task.ps1`. Runs every minute, auto-restarts unhealthy services, only alerts Discord when auto-recovery fails.

## Install on Windows

```powershell
# One-shot — installs all three services, then schedules the health monitor.
powershell -ExecutionPolicy Bypass -File D:\mercury\scripts\windows-services\install-services.ps1
powershell -ExecutionPolicy Bypass -File D:\mercury\scripts\health-monitor\install-task.ps1

# Optional: install the TUI dependencies
uv pip install -r D:\mercury\scripts\rtk_tui\requirements.txt
```

Both scripts self-elevate. The first one will prompt for your Windows password
once — NSSM needs it to set the services' `ObjectName` to your interactive
user, which is required because the services need access to `~/.cloudflared/`,
`~/.mercury/`, and `~/.cortex/`.

Set `MERCURY_ALERT_WEBHOOK_URL` (machine env var) before running the health
monitor if you want Discord alerts on auto-recovery failure.

## Install on Linux

```bash
cd D:/mercury/scripts/linux-services
chmod +x install.sh
./install.sh

cd ../health-monitor
chmod +x install-cron.sh
./install-cron.sh
```

## Day-2 operations

### Status

```powershell
Get-Service rtk-* | Format-Table Name, Status, StartType -AutoSize
# or
python -m rtk_tui
```

### Restart after a `git pull`

```powershell
Restart-Service rtk-mercury-gateway   # picks up new mercury code
Restart-Service rtk-cortex-webapp     # picks up new cortex code
```

Cloudflared restarts only when its `~/.cloudflared/config.yml` changes:

```powershell
Restart-Service rtk-cloudflared
```

Or use the helper to bounce all three in dependency order:

```powershell
powershell -ExecutionPolicy Bypass -File D:\mercury\scripts\windows-services\restart-all.ps1
```

### View logs

```powershell
Get-Content -Path "$env:USERPROFILE\.mercury\logs\gateway.out.log" -Tail 50 -Wait
Get-Content -Path "$env:USERPROFILE\.cortex\logs\webapp.err.log" -Tail 50 -Wait
Get-Content -Path "$env:USERPROFILE\.cloudflared\service.log" -Tail 50 -Wait
```

The TUI tails whichever log corresponds to the highlighted service automatically.

## What gets restarted automatically vs. what needs you

**Automatic recovery:**
- Process crash (any non-zero exit) → NSSM restarts after a 60s throttle, up to 5 attempts per hour.
- Unhealthy `/api/health` or zero tunnel connections → health monitor restarts within 60s and re-probes after 30s grace.

**Needs manual intervention:**
- Cloudflared cert expired (`~/.cloudflared/cert.pem`) → re-auth via `cloudflared tunnel login`.
- Tunnel credentials missing → re-create the tunnel: `cloudflared tunnel create rtk-5090` and update `config.yml`.
- Mercury venv broken (e.g. Python upgrade) → `uv sync` from `D:\mercury` and `Restart-Service rtk-mercury-gateway`.
- Cortex model weights not downloaded → `python D:\cortex\scripts\fetch_weights.py` then restart.
- Five restarts in an hour without recovery → NSSM stops auto-restarting; check `.err.log`, fix, then `Restart-Service` manually.
- Discord token revoked / regenerated → update `~/.mercury/.env` and restart.

## Failure scenarios cheat sheet

| Symptom                                  | Probable cause                              | Fix                                                                                       |
|------------------------------------------|---------------------------------------------|-------------------------------------------------------------------------------------------|
| `mercury.redteamkitchen.com` 502         | tunnel down                                 | check `~/.cloudflared/service.log`; `Restart-Service rtk-cloudflared`                     |
| Mercury bot offline in Discord           | gateway crashed at boot                     | `~/.mercury/logs/gateway.err.log` — usually missing env var or token                      |
| Cortex 503 on `/api/generate`            | scheduler stuck or VRAM full                | check GPU panel in TUI; `Restart-Service rtk-cortex-webapp`                               |
| Health monitor hammering #alerts         | a service won't recover                     | stop the task: `Disable-ScheduledTask -TaskName rtk-health-monitor`; investigate root cause |
| All three services flapping              | machine likely OOM / disk full              | `Get-Volume`, `Get-Process \| Sort-Object WS -Desc \| select -first 10`                   |

## Cost

Local services: free. Discord alert webhook: free. The only ongoing spend
is the residential Internet + power, which is unrelated to this stack.

## Constraints worth remembering

- All scripts are idempotent — re-running them after a `git pull` is the
  intended upgrade path.
- Scripts use absolute paths exclusively, so they work whether you call
  them from `cmd.exe`, PowerShell, or git-bash.
- No secrets are committed. `DISCORD_BOT_TOKEN` lives in `~/.mercury/.env`
  (or `~/.hermes/.env`), `MERCURY_ALERT_WEBHOOK_URL` lives in machine env
  vars, and `~/.cloudflared/cert.pem` stays on disk only.
