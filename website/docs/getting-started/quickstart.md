---
sidebar_position: 1
title: "Quickstart"
description: "Your first conversation with Mercury Agent — from install to chatting in under 5 minutes"
---

# Quickstart

This guide gets you from zero to a working Mercury setup that survives real use. Install, choose a provider, verify a working chat, and know exactly what to do when something breaks.

## Who this is for

- Brand new and want the shortest path to a working setup
- Switching providers and don't want to lose time to config mistakes
- Setting up Mercury for a team, bot, or always-on workflow
- Tired of "it installed, but it still does nothing"

## The fastest path

Pick the row that matches your goal:

| Goal | Do this first | Then do this |
|---|---|---|
| I just want Mercury working on my machine | `mercury setup` | Run a real chat and verify it responds |
| I already know my provider | `mercury model` | Save the config, then start chatting |
| I want a bot or always-on setup | `mercury gateway setup` after CLI works | Connect Telegram, Discord, Slack, or another platform |
| I want a local or self-hosted model | `mercury model` → custom endpoint | Verify the endpoint, model name, and context length |
| I want multi-provider fallback | `mercury model` first | Add routing and fallback only after the base chat works |

**Rule of thumb:** if Mercury cannot complete a normal chat, do not add more features yet. Get one clean conversation working first, then layer on gateway, cron, skills, voice, or routing.

---

## 1. Install Mercury Agent

Run the one-line installer:

```bash
# Linux / macOS / WSL2 / Android (Termux)
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

:::tip Android / Termux
If you're installing on a phone, see the dedicated [Termux guide](./termux.md) for the tested manual path, supported extras, and current Android-specific limitations.
:::

:::tip Windows Users
Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) first, then run the command above inside your WSL2 terminal.
:::

After it finishes, reload your shell:

```bash
source ~/.bashrc   # or source ~/.zshrc
```

For detailed installation options, prerequisites, and troubleshooting, see the [Installation guide](./installation.md).

## 2. Choose a Provider

The single most important setup step. Use `mercury model` to walk through the choice interactively:

```bash
mercury model
```

Good defaults:

| Situation | Recommended path |
|---|---|
| Least friction | Nous Portal or OpenRouter |
| You already have Claude or Codex auth | Anthropic or OpenAI Codex |
| You want local/private inference | Ollama or any custom OpenAI-compatible endpoint |
| You want multi-provider routing | OpenRouter |
| You have a custom GPU server | vLLM, SGLang, LiteLLM, or any OpenAI-compatible endpoint |

For most first-time users: choose a provider, accept the defaults unless you know why you're changing them. The full provider catalog with env vars and setup steps lives on the [Providers](../integrations/providers.md) page.

:::caution Minimum context: 64K tokens
Mercury Agent requires a model with at least **64,000 tokens** of context. Models with smaller windows cannot maintain enough working memory for multi-step tool-calling workflows and will be rejected at startup. Most hosted models (Claude, GPT, Gemini, Qwen, DeepSeek) meet this easily. If you're running a local model, set its context size to at least 64K (e.g. `--ctx-size 65536` for llama.cpp or `-c 65536` for Ollama).
:::

:::tip
You can switch providers at any time with `mercury model` — no lock-in. For a full list of all supported providers and setup details, see [AI Providers](../integrations/providers.md).
:::

### How settings are stored

Mercury separates secrets from normal config:

- **Secrets and tokens** → `~/.mercury/.env`
- **Non-secret settings** → `~/.mercury/config.yaml`

The easiest way to set values correctly is through the CLI:

```bash
mercury config set model anthropic/claude-opus-4.6
mercury config set terminal.backend docker
mercury config set OPENROUTER_API_KEY sk-or-...
```

The right value goes to the right file automatically.

## 3. Run Your First Chat

```bash
mercury            # classic CLI
mercury --tui      # modern TUI (recommended)
```

You'll see a welcome banner with your model, available tools, and skills. Use a prompt that's specific and easy to verify:

:::tip Pick your interface
Mercury ships with two terminal interfaces: the classic `prompt_toolkit` CLI and a newer [TUI](../user-guide/tui.md) with modal overlays, mouse selection, and non-blocking input. Both share the same sessions, slash commands, and config — try each with `mercury` vs `mercury --tui`.
:::

```
Summarize this repo in 5 bullets and tell me what the main entrypoint is.
```

```
Check my current directory and tell me what looks like the main project file.
```

```
Help me set up a clean GitHub PR workflow for this codebase.
```

**What success looks like:**

- The banner shows your chosen model/provider
- Mercury replies without error
- It can use a tool if needed (terminal, file read, web search)
- The conversation continues normally for more than one turn

If that works, you're past the hardest part.

## 4. Verify Sessions Work

Before moving on, make sure resume works:

```bash
mercury --continue    # Resume the most recent session
mercury -c            # Short form
```

That should bring you back to the session you just had. If it doesn't, check whether you're in the same profile and whether the session actually saved. This matters later when you're juggling multiple setups or machines.

## 5. Try Key Features

### Use the terminal

```
❯ What's my disk usage? Show the top 5 largest directories.
```

The agent runs terminal commands on your behalf and shows results.

### Slash commands

Type `/` to see an autocomplete dropdown of all commands:

| Command | What it does |
|---------|-------------|
| `/help` | Show all available commands |
| `/tools` | List available tools |
| `/model` | Switch models interactively |
| `/personality pirate` | Try a fun personality |
| `/save` | Save the conversation |

### Multi-line input

Press `Alt+Enter` or `Ctrl+J` to add a new line. Great for pasting code or writing detailed prompts.

### Interrupt the agent

If the agent is taking too long, type a new message and press Enter — it interrupts the current task and switches to your new instructions. `Ctrl+C` also works.

## 6. Add the Next Layer

Only after the base chat works. Pick what you need:

### Bot or shared assistant

```bash
mercury gateway setup    # Interactive platform configuration
```

Connect [Telegram](/docs/user-guide/messaging/telegram), [Discord](/docs/user-guide/messaging/discord), [Slack](/docs/user-guide/messaging/slack), [WhatsApp](/docs/user-guide/messaging/whatsapp), [Signal](/docs/user-guide/messaging/signal), [Email](/docs/user-guide/messaging/email), or [Home Assistant](/docs/user-guide/messaging/homeassistant).

### Automation and tools

- `mercury tools` — tune tool access per platform
- `mercury skills` — browse and install reusable workflows
- Cron — only after your bot or CLI setup is stable

### Sandboxed terminal

For safety, run the agent in a Docker container or on a remote server:

```bash
mercury config set terminal.backend docker    # Docker isolation
mercury config set terminal.backend ssh       # Remote server
```

### Voice mode

```bash
pip install "mercury-agent[voice]"
# Includes faster-whisper for free local speech-to-text
```

Then in the CLI: `/voice on`. Press `Ctrl+B` to record. See [Voice Mode](../user-guide/features/voice-mode.md).

### Skills

```bash
mercury skills search kubernetes
mercury skills install openai/skills/k8s
```

Or use `/skills` inside a chat session.

### MCP servers

```yaml
# Add to ~/.mercury/config.yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxx"
```

### Editor integration (ACP)

```bash
pip install -e '.[acp]'
mercury acp
```

See [ACP Editor Integration](../user-guide/features/acp.md).

---

## Common Failure Modes

These are the problems that waste the most time:

| Symptom | Likely cause | Fix |
|---|---|---|
| Mercury opens but gives empty or broken replies | Provider auth or model selection is wrong | Run `mercury model` again and confirm provider, model, and auth |
| Custom endpoint "works" but returns garbage | Wrong base URL, model name, or not actually OpenAI-compatible | Verify the endpoint in a separate client first |
| Gateway starts but nobody can message it | Bot token, allowlist, or platform setup is incomplete | Re-run `mercury gateway setup` and check `mercury gateway status` |
| `mercury --continue` can't find old session | Switched profiles or session never saved | Check `mercury sessions list` and confirm you're in the right profile |
| Model unavailable or odd fallback behavior | Provider routing or fallback settings are too aggressive | Keep routing off until the base provider is stable |
| `mercury doctor` flags config problems | Config values are missing or stale | Fix the config, retest a plain chat before adding features |

## Recovery Toolkit

When something feels off, use this order:

1. `mercury doctor`
2. `mercury model`
3. `mercury setup`
4. `mercury sessions list`
5. `mercury --continue`
6. `mercury gateway status`

That sequence gets you from "broken vibes" back to a known state fast.

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `mercury` | Start chatting |
| `mercury model` | Choose your LLM provider and model |
| `mercury tools` | Configure which tools are enabled per platform |
| `mercury setup` | Full setup wizard (configures everything at once) |
| `mercury doctor` | Diagnose issues |
| `mercury update` | Update to latest version |
| `mercury gateway` | Start the messaging gateway |
| `mercury --continue` | Resume last session |

## Next Steps

- **[CLI Guide](../user-guide/cli.md)** — Master the terminal interface
- **[Configuration](../user-guide/configuration.md)** — Customize your setup
- **[Messaging Gateway](../user-guide/messaging/index.md)** — Connect Telegram, Discord, Slack, WhatsApp, Signal, Email, or Home Assistant
- **[Tools & Toolsets](../user-guide/features/tools.md)** — Explore available capabilities
- **[AI Providers](../integrations/providers.md)** — Full provider list and setup details
- **[Skills System](../user-guide/features/skills.md)** — Reusable workflows and knowledge
- **[Tips & Best Practices](../guides/tips.md)** — Power user tips
