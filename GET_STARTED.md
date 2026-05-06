# Mercury — Get Started

**For a teacher with a recent MacBook or any modern PC. From clone to first chat in under 5 minutes.**

## What you need

- A computer with at least 8 GB RAM (for Gemma 4 E2B, the smallest model). 16 GB if you want E4B (the default). 32 GB+ if you want vision and audio understanding at full quality.
- One of: macOS (M-series preferred), Linux, or Windows with WSL2.
- 10 GB free disk for the model weights.
- That's it. **No API key. No cloud account. No credit card.**

## The single-command flow

```bash
# 1. Clone the repo
git clone https://github.com/AlexiosBluffMara/mercury.git && cd mercury

# 2. Run setup — picks the right path for your OS, installs Mercury + a Gemma model
./scripts/setup.sh

# 3. Talk to it
mercury -z "What's 2 + 2 and why?"
```

That's the full path. `setup.sh` decides:
- Mac with M-series → installs `uv` if missing, runs `uv pip install -e .`, pulls a Gemma 4 model via Ollama (or downloads MLX weights for native Mac acceleration)
- Linux/Windows-WSL2 with NVIDIA GPU → installs `uv`, sets up Mercury, pulls the Gemma 4 E4B model via Ollama
- Anything else → installs Mercury and falls back to OpenRouter's `:free` Gemma 4 tier (1000 free reqs/day if you set up an OpenRouter account; otherwise 50/day per IP)

## What you get

After setup:

- **`mercury -z "your question"`** — one-shot from the terminal
- **`mercury chat`** — interactive TUI with conversation history
- **`mercury dashboard`** — open a chat web UI at http://localhost:9119
- **`mercury gateway run`** — start the agent gateway that wires Mercury into Discord, WhatsApp, and any other channel you've configured

## What runs where

| If you have... | Mercury picks... | Cost |
|---|---|---|
| M-series Mac + 8+ GB | Gemma 4 E4B via MLX, ~145 tok/s | $0 |
| M-series Mac + 32+ GB | Gemma 4 31B via MLX, native vision and audio | $0 |
| NVIDIA GPU 8+ GB | Gemma 4 E4B via Ollama CUDA, ~194 tok/s | $0 |
| Anything older | OpenRouter `:free` tier Gemma 4 26B (rate-limited) | $0 |
| Two+ machines on the same WiFi | Mercury auto-discovers and uses the best one | $0 |

Mercury **falls over automatically** when one path goes down. Pull the Ethernet cable on your fast machine, and Mercury keeps answering on the slower one. Pull the WiFi entirely, and Mercury keeps answering with whatever local model fits.

## Five doors, one Mercury

After `mercury gateway run`, you can also reach Mercury through:

- **Discord** — invite Snowy The Bot to any server. Configured at `~/.mercury/config.yaml`.
- **WhatsApp** — DM your own number to talk to your own Mercury (self-chat mode, no second number needed).
- **Web UI** — http://localhost:9119, mobile-friendly, dark-mode by default.
- **Any other channel** — Mercury exposes an OpenAI-compatible API at `http://localhost:9119/v1/chat/completions`. Plug it into anything that talks to OpenAI.

## Memory is yours

Conversations live at `~/.mercury/state.db` (SQLite). Skill outputs live at `~/.mercury/vault/` as plain markdown — open in Obsidian if you want a wiki view. Back up either of those and you've moved your Mercury.

## Cost

After the first 10 GB download, Mercury costs ~$0.02/hour at idle on US grid power. Most homes pay less than $5/month for it running 24/7 — and it only does work when you ask, so the real cost is closer to the cost of a smartphone background task.

There is no per-token bill, no monthly subscription, no usage cap beyond what your hardware can sustain. **Gemma 4 is Apache 2.0 open-weight; the only "API key" Mercury asks you for is OpenRouter's, and that's optional and free.**

## What about the rest of the README?

This file is the "what does it look like the first time" version. The full architecture, the dual-hackathon submission notes, the cost analysis vs an API-only competitor, and the cloud-mirror plan all live in:

- [`README.md`](README.md) — the full project overview
- [`SUBMISSION_GEMMA4.md`](SUBMISSION_GEMMA4.md) — the Gemma 4 Good Hackathon technical writeup
- [`docs/HACKATHON_COSTS_2026-05-06.md`](docs/HACKATHON_COSTS_2026-05-06.md) — line-item cost analysis
- [`docs/CLOUD_REPLICATION_2026-05-06.md`](docs/CLOUD_REPLICATION_2026-05-06.md) — full cloud mirror plan
- [`docs/MERCURY_CORTEX_CONTRACT.md`](docs/MERCURY_CORTEX_CONTRACT.md) — how Mercury and Cortex share the same GPU
- [`docs/SELF_UPDATE_LOOP_2026-05-06.md`](docs/SELF_UPDATE_LOOP_2026-05-06.md) — how Mercury self-improves nightly

## License

Apache 2.0 — same as Gemma 4 itself.
