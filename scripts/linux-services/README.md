# Linux user-systemd services

Mirrors the Windows NSSM setup for Linux/WSL/HPC nodes. Each service runs
under the user's systemd instance (`systemctl --user`), so no root needed
for daily operation; the only privileged step is `loginctl enable-linger`
once, so services start without an active login session.

## Layout

| Unit                          | What it runs                                                          |
|-------------------------------|-----------------------------------------------------------------------|
| `rtk-cloudflared.service`     | `cloudflared tunnel --config ~/.cloudflared/config.yml run rtk-5090`  |
| `rtk-cortex-webapp.service`   | `~/cortex/.venv/bin/python -m uvicorn webapp.server:app --host 0.0.0.0 --port 8765` |
| `rtk-mercury-gateway.service` | `~/mercury/.venv/bin/python -m mercury_cli gateway run -v`            |

All three: `Type=simple`, `Restart=on-failure`, `RestartSec=60s`,
`StartLimitBurst=5` per `StartLimitIntervalSec=3600`. Logs to
`~/.{cloudflared,cortex,mercury}/...` (mirrors Windows) and `journalctl`.

## Install

```bash
cd D:/mercury/scripts/linux-services    # or wherever the repo is checked out
chmod +x install.sh
./install.sh
```

Idempotent — run it again after a `git pull` to refresh the unit files.

## Day-2 commands

```bash
# Status
systemctl --user status rtk-mercury-gateway

# Tail logs (live)
journalctl --user -u rtk-mercury-gateway -f

# Restart one
systemctl --user restart rtk-mercury-gateway

# Restart all in dependency order
systemctl --user restart rtk-cloudflared rtk-cortex-webapp rtk-mercury-gateway

# Disable / stop
systemctl --user disable --now rtk-mercury-gateway
```
