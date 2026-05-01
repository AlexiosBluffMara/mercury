# Windows services (NSSM-wrapped)

Wraps the three long-running RTK services into Windows services that boot
with the machine and auto-restart on crash.

## What's installed

| Service              | What it runs                                                                                  | AppDirectory          | Logs                                |
|----------------------|-----------------------------------------------------------------------------------------------|-----------------------|-------------------------------------|
| `rtk-cloudflared`    | `cloudflared.exe tunnel --config ~/.cloudflared/config.yml run rtk-5090`                      | `%USERPROFILE%`       | `~/.cloudflared/service.log`        |
| `rtk-cortex-webapp`  | `C:\Users\soumi\cortex\.venv\Scripts\python.exe -m uvicorn webapp.server:app --host 0.0.0.0 --port 8765` | `D:\cortex`           | `~/.cortex/logs/webapp.{out,err}.log` |
| `rtk-mercury-gateway`| `D:\mercury\.venv\Scripts\python.exe -m mercury_cli gateway run -v`                            | `D:\mercury`          | `~/.mercury/logs/gateway.{out,err}.log` |

Restart policy on every service:
- Restart on any non-zero exit
- 60s throttle (don't hammer-restart a broken process)
- Max 5 restarts per 1-hour window
- 10 MB log rotation

All three are `SERVICE_AUTO_START` (Windows boot) and run as the current
interactive user, so paths like `~/.cloudflared/`, `~/.mercury/`, and
`~/.cortex/` resolve correctly.

## Install

```powershell
# From an elevated PowerShell (the script self-elevates if not):
powershell -ExecutionPolicy Bypass -File D:\mercury\scripts\windows-services\install-services.ps1
```

The script:
1. Detects NSSM. If missing, downloads `nssm-2.24.zip`, extracts the
   matching arch (`win64`/`win32`) into `C:\Program Files\nssm`, adds it
   to `PATH`.
2. Installs (or updates) the three services.
3. Sets all NSSM parameters idempotently — safe to re-run.
4. Starts each and prints status from both `Get-Service` and `nssm status`.

When NSSM sets `ObjectName` (the run-as account) to your interactive user,
Windows will prompt for your password. There's no way around this — services
that need access to `~/.cloudflared/` must run as you, not `LocalSystem`.

## Day-2 commands

```powershell
# Status
Get-Service rtk-* | Format-Table Name, Status, StartType -AutoSize

# Tail a log live
Get-Content -Path "$env:USERPROFILE\.mercury\logs\gateway.out.log" -Tail 50 -Wait

# Restart one
Restart-Service rtk-mercury-gateway

# Restart all in dependency order (tunnel -> cortex -> mercury)
powershell -ExecutionPolicy Bypass -File D:\mercury\scripts\windows-services\restart-all.ps1

# Uninstall
powershell -ExecutionPolicy Bypass -File D:\mercury\scripts\windows-services\uninstall-services.ps1
```

## Updating after a `git pull`

Code changes don't auto-deploy. After pulling new mercury or cortex code:

```powershell
Restart-Service rtk-mercury-gateway   # picks up the new code
Restart-Service rtk-cortex-webapp
```

Config-only changes to `~/.cloudflared/config.yml` need:

```powershell
Restart-Service rtk-cloudflared
```

## Troubleshooting

| Symptom                              | Where to look                                                |
|--------------------------------------|--------------------------------------------------------------|
| Service won't start                  | `nssm status <svc>` and the `*.err.log` for that service     |
| `cloudflared` tunnel has 0 conns     | `~/.cloudflared/service.log`. Cert expired? `~/.cloudflared/cert.pem` re-auth |
| Mercury gateway crashes on boot      | `~/.mercury/logs/gateway.err.log`. Most likely missing `~/.mercury/.env` (`DISCORD_BOT_TOKEN`) |
| Cortex webapp crashes on boot        | `~/.cortex/logs/webapp.err.log`. Most likely venv broken or model weights not downloaded |
| Service flapping (5 restarts/hour)   | NSSM gives up after 5 restarts in 1h. Check the err log, fix, then `Restart-Service` |
