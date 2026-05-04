# Pixel 9 Pro Fold — Mercury Tailnet Onboarding

The mobile half of Mercury's mesh. The Pixel 9 Pro Fold (Tensor G4, 16 GB
RAM) hosts a local Mercury client via Termux, a WhatsApp gateway, and an
on-device Gemma 4 E4B for offline narration when the tailnet is unreachable.

---

## What runs where

| Surface | Where it lives on the phone | Purpose |
|---|---|---|
| Mercury CLI | `~/mercury` (Termux pkg + venv) | The agent, talking to the GPU host over the tailnet |
| Mercury Agent (full) | same venv | Skills runtime |
| WhatsApp gateway | Termux daemon under `mercury gateway up whatsapp` | Bridges WhatsApp → Mercury → brain pipeline |
| Local Gemma 4 E4B | MediaPipe LLM Inference + Q4_K_XL `.task` file in `~/storage/shared/llm/` | Offline narration when tailnet is down |
| Tailscale | Play Store Tailscale app | Mesh membership |

## Setup, end to end

### 1) Install Termux (the right one)

**Use the [F-Droid Termux](https://f-droid.org/en/packages/com.termux/), not the Play Store version.** The Play Store Termux is unmaintained and won't `pkg update` cleanly.

```bash
# Inside Termux:
pkg update && pkg upgrade
pkg install -y python git rust openssl libffi clang make
termux-setup-storage          # grants Termux access to ~/storage
```

### 2) Install Mercury

```bash
cd ~
git clone https://github.com/AlexiosBluffMara/mercury
cd mercury
python -m venv .venv
source .venv/bin/activate
pip install -e .[termux]      # NOTE: `.[all]` pulls Android-incompat voice deps
```

The `.[termux]` extra is the Mercury / Mercury Agent recommended set for
Android — it skips `pyaudio`, `whisper`, and similar deps that don't
build on Termux.

### 3) Install Tailscale

Install the [Tailscale Android app](https://play.google.com/store/apps/details?id=com.tailscale.ipn) from the Play Store. Sign in with the same email that owns the tailnet (`soumitlahiri@philanthropytraders.com`).

In the Tailscale admin (`https://login.tailscale.com/admin/machines`):
- Find this device (named something like `Pixel-9-Pro-Fold-...`)
- Edit Tags → add `tag:mobile`
- Edit Route Settings → enable subnet routing if you want this device to
  reach `tag:gpu`'s LAN beyond the tailnet (usually unnecessary)

Verify reachability:
```bash
# In Termux
tailscale status                  # should list your gpu host
ping -c 3 <gpu-host-tailscale-ip>
```

### 4) Configure Mercury for the mobile env

```bash
# Tell Mercury where to reach the GPU host's API
echo 'export MERCURY_API_URL=http://<gpu-host-tailscale-ip>:8765' >> ~/.bashrc
echo 'export NOUS_API_KEY=sk-...' >> ~/.bashrc
source ~/.bashrc

mercury setup                     # interactive — pick "Nous Portal" provider
mercury status                    # confirm everything connects
```

### 5) Wire WhatsApp

```bash
mercury gateway up whatsapp
```

The first run prints a QR code. Open WhatsApp on the phone (yes, the same
phone — open WhatsApp normally) and scan the QR via *Settings → Linked
Devices → Link a Device*. Mercury now relays WhatsApp messages to the
agent loop, including the brain-viz `/brain` command.

### 6) Optional: install local Gemma 4 E4B via MediaPipe

For offline narration when the tailnet is down (e.g. you're on a plane):

```bash
# Download the Q4_K_XL .task file (~5 GB) onto the phone
termux-open --view <https://huggingface.co/google/gemma-3-4b-it-q4_k_xl-mlc/...>

# Place at ~/storage/shared/llm/gemma-4-e4b-it.task
# Mercury auto-discovers it on next startup
```

The MediaPipe runtime sips ~5 GB RAM during inference; the phone's 16 GB
total comfortably accommodates it alongside WhatsApp, Tailscale, Chrome,
and Mercury itself.

## Verification

From the GPU host (Windows 11):

```bash
# In a fresh shell where NOUS_API_KEY is loaded
mercury -z "Reply: tailnet alive" --provider nous-portal --model moonshotai/kimi-k2.6
```

From the Pixel (Termux):

```bash
mercury -z "Reply: pixel alive"   # routes through tailnet to GPU host's Mercury
```

Both should return cleanly. If the Pixel call hangs, check Tailscale's
"Direct" vs "Relay" indicator — relay is fine but slower; direct means
NAT traversal succeeded.

## Hard Invariants (matches `tailnet/SKILL.md`)

1. **Tailnet-only.** Never expose the Pixel's Mercury via Funnel.
2. **Identity middleware** — when the Pixel calls into the GPU host's
   `/api/mercury/*` routes, the `Tailscale-User-Login` header is asserted
   automatically. Never bypass.
3. **No keystore copies.** The `NOUS_API_KEY` and `DISCORD_BOT_TOKEN` live
   in the phone's `~/.bashrc` and are NOT synced to GPU-host config. Loss
   of phone = revoke and rotate, not "restore from backup."

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `mercury: command not found` after install | Termux's PATH didn't pick up `.venv/bin` | `source ~/mercury/.venv/bin/activate` and re-add to `~/.bashrc` |
| Slash commands not appearing in WhatsApp | Gateway not running, or QR never scanned | `mercury gateway status whatsapp` should show `connected` |
| `tailscale ping` says "no route" | The phone's Tailscale isn't actually on, or device not tagged | Open the Tailscale app, toggle on; check admin tags |
| Calls to GPU host time out | GPU host firewall blocking 8765 | Allow inbound 8765 from `tag:mobile` only — ACL handles this if your firewall trusts Tailscale's interface |
| Local Gemma 4 fails to load | `.task` file in wrong location, or RAM constrained | Move to internal storage (faster), close Chrome |
