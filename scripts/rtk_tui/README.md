# `rtk_tui` — operator console for the RTK 5090 stack

Live status + restart control for the three rtk-* services in one
Textual TUI. Works locally on the 5090 and equally well over SSH from
another machine (Textual auto-detects terminal capabilities).

## Install

From the repo root:

```bash
uv pip install -r D:\mercury\scripts\rtk_tui\requirements.txt
# or, if you prefer pip:
pip install -r D:\mercury\scripts\rtk_tui\requirements.txt
```

## Run

```bash
cd D:\mercury\scripts
python -m rtk_tui
```

## What you see

- **Top-left**: services table (cloudflared / cortex-webapp / mercury-gateway) with live state — green = running, red = stopped/errored, blue = transitioning.
- **Top-right**: tunnel connection count, cortex `/api/health`, mercury `/api/health`, and GPU state polled from `http://localhost:8765/api/utilization` (free VRAM, scheduler state, queue depth).
- **Middle**: live tail of the highlighted service's log.
- **Bottom (toggle with `t`)**: test panel — type a prompt, hit Enter, see the response from mercury or cortex (Tab cycles target).

## Hotkeys

| key | action                                                      |
|-----|-------------------------------------------------------------|
| `r` | Restart highlighted service                                 |
| `R` | Restart **all** in dependency order (cloudflared first)     |
| `s` | Stop highlighted service                                    |
| `l` | Cycle the log stream shown for the highlighted service (`out` <-> `err`) |
| `t` | Toggle the test panel                                       |
| `q` | Quit (services keep running)                                |

## Polling cadence

| Probe                         | Interval |
|-------------------------------|----------|
| Service status (sc.exe / systemctl) | 3 s |
| GPU utilization               | 3 s |
| cortex / mercury `/api/health`| 3 s |
| `cloudflared tunnel info`     | 5 s |
| Log tail of highlighted svc   | 1 s |

## SSH / headless

Textual works over plain SSH. If colors look wrong, `export TERM=xterm-256color`
before launching.
