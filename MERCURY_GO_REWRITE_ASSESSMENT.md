# Mercury → Go: rewrite assessment

**Date**: 2026-05-04
**Scope**: A pure-Go rewrite of Mercury (currently 184k LOC Python + 60k LOC TypeScript). This document is **the assessment**, not the instructions to start coding. It enumerates every component, the Go library we'd use to replace it, the effort estimate, and the right sequence.

> Companion: `MERCURY_GO_WIKI.md` (learning the language) · `LANGUAGE_COMPARISON.md` (deeper trade-off analysis) · `SUMMER_COURSE_PLAN.md` (the curriculum that uses this rewrite as the practice project).

---

## 0. Total scope at a glance

```
┌────────────────────────────────────────────────────────────────────┐
│  Mercury today                                                      │
│  ─────────────                                                       │
│  Python   : 1,115 files, 183,906 LOC                                │
│  TypeScript: 333 files,  59,852 LOC  (mercury-web SPA + ui-tui Ink) │
│  Total    :  ~244 KLOC                                              │
│                                                                       │
│  Pure-Go target                                                       │
│  ──────────────                                                       │
│  Estimated Go LOC: ~85 KLOC                                          │
│   (Go is more verbose than Python per concept but vastly less than   │
│   the equivalent Python+TS combined — stdlib does what Mercury       │
│   pulls 18+ deps for, and we drop the React layer entirely.)         │
│                                                                       │
│  Calendar effort, 1 engineer, no breaks: ~6 months                   │
│  Calendar effort, 1 engineer, w/ summer course (15 hr/wk): ~9 months │
│                                                                       │
│  Realistic plan: incremental, ship every 2 weeks                      │
└────────────────────────────────────────────────────────────────────┘
```

We **don't** rewrite all of it. The right outcome is a hybrid:
- **Go** for the daemon, the gateway, the TUI, the CLI dispatcher, the watchdog, and any infra-shaped code.
- **Python** stays for the agent loop core (LLM SDKs are best-in-class in Python), skills/plugins (markdown + Python is the right author surface), and ML glue (TRIBE, Whisper, Ollama clients).
- **HTMX or SolidJS** for the dashboard SPA, replacing the React build.

The "rewrite in Go" framing is therefore: **rewrite the operating skin around the agent**, not the agent itself.

---

## 1. Module-by-module inventory

Module size in current Mercury LOC. Effort in **engineer-days** assuming the engineer is fluent in Go (week 8+ of the summer course). Add 30-50% for an engineer still learning.

| # | Mercury module | Current LOC | Go target LOC | Library/approach | Effort |
|---|---|---:|---:|---|---:|
| 1 | `mercury-status` (one subcommand) | 200 | 80 | `net/http` + `fmt` + `lipgloss` | **0.5 d** |
| 2 | `mercury-watchdog` (Sera fleet healer) | 350 | 200 | `os/exec` + `net/http` | 1 d |
| 3 | `mercury` CLI dispatcher (entry point only) | 500 | 250 | `cobra` | 1 d |
| 4 | `mercury config` (read/write config.yaml) | 800 | 400 | `gopkg.in/yaml.v3` | 1 d |
| 5 | `mercury auth` (provider OAuth) | 4,300 | 2,800 | `golang.org/x/oauth2` + per-provider | 5 d |
| 6 | `mercury sessions` (list, search, replay) | 2,000 | 1,200 | `mattn/go-sqlite3` | 3 d |
| 7 | `mercury memory` (memory_manager) | 1,800 | 1,000 | `mattn/go-sqlite3` + `sashabaranov/go-openai` for embeddings | 3 d |
| 8 | `mercury logs` + `mercury insights` | 1,200 | 600 | `slog` + custom queryer | 2 d |
| 9 | `mercury cron` | 900 | 500 | `robfig/cron/v3` | 1 d |
| 10 | `mercury hooks` | 1,000 | 600 | `os/exec` (just shells out) | 1 d |
| 11 | `mercury webhook` | 800 | 500 | `net/http` (server) | 1 d |
| 12 | `mercury mcp` (MCP client + server) | 3,000 | 1,800 | hand-rolled JSON-RPC over stdio (~spec is small) | 5 d |
| 13 | `mercury plugins` (loader + IPC) | 2,000 | 1,200 | Unix sockets / named pipes | 4 d |
| 14 | `mercury skills` (markdown loader, search) | 1,500 | 800 | `bluele/gcache` for index, `os.ReadDir` | 2 d |
| 15 | `mercury kanban` (multi-board) | 1,600 | 1,000 | sqlite + simple HTTP | 3 d |
| 16 | TUI (`ui-tui/packages/mercury-ink/`) | 35,000 LOC TS | 8,000 LOC Go | `bubbletea` + `lipgloss` + `bubbles` | **20 d** |
| 17 | `tui_gateway/server.py` (TUI websocket bridge) | 4,600 | 1,500 | `coder/websocket` + `slog` | 4 d |
| 18 | `gateway/run.py` (gateway main loop) | 11,100 | 4,500 | goroutine-per-platform pattern | **15 d** |
| 19 | `gateway/platforms/discord.py` | 4,200 | 2,000 | `bwmarrin/discordgo` | 8 d |
| 20 | `gateway/platforms/email.py` | ~1,500 | 600 | `net/smtp` + `emersion/go-imap` | 3 d |
| 21 | `gateway/platforms/whatsapp.py` | ~1,200 | 600 | `tulir/whatsmeow` | 3 d |
| 22 | `gateway/platforms/webhook.py` | ~800 | 400 | `net/http` | 1 d |
| 23 | `gateway/platforms/api_server.py` | ~1,000 | 500 | `net/http` | 2 d |
| 24 | `agent/auxiliary_client.py` (delegate spawn) | 3,400 | 2,000 | `os/exec` + IPC | 6 d |
| 25 | `agent/credential_pool.py` | 1,500 | 800 | `mattn/go-sqlite3` | 3 d |
| 26 | `agent/context_compressor.py` | 1,300 | 700 | hand-roll | 3 d |
| 27 | `agent/anthropic_adapter.py` | 1,700 | 1,000 | `anthropics/anthropic-sdk-go` | 3 d |
| 28 | `agent/gemini_native_adapter.py` | ~1,200 | 700 | `google.golang.org/genai` | 3 d |
| 29 | `agent/codex_responses_adapter.py` (OpenAI Responses API) | ~1,400 | 800 | `openai/openai-go` | 3 d |
| 30 | `tools/browser_tool.py` (Patchright) | ~3,000 | 2,500 | `chromedp/chromedp` | 8 d |
| 31 | `tools/code_execution_tool.py` (sandboxed exec) | ~1,500 | 1,000 | `os/exec` + bwrap/sandbox-exec | 5 d |
| 32 | `tools/file_*` (read/write/edit/find) | ~3,000 | 1,500 | `os` + `bufio` | 3 d |
| 33 | `tools/delegate_tool.py` | ~600 | 400 | shells out to subagent | 1 d |
| 34 | The 12k-LOC `run_agent.py` (top-level loop) | 12,700 | 5,000 | refactor + port | **15 d** |
| 35 | The 11k-LOC `cli.py` (interactive REPL) | 11,100 | 3,500 | `chzyer/readline` or `bubbletea` interactive | 8 d |
| 36 | Web dashboard server (Python FastAPI) | 4,000 | 2,000 | `net/http` + templates | 4 d |
| 37 | Web dashboard SPA (React+Vite) | 35,000 LOC TS | rewrite | **HTMX + Go templates** OR `solidjs` (still TS) | **20 d** |
| 38 | Skills (markdown — left as-is) | 837 .md | unchanged | shipped as data | 0 d |
| 39 | Plugins (Python — left as-is OR rewritten per-plugin) | varies | varies | each plugin: own decision | varies |
| 40 | Tests (port pytest → go test) | ~30,000 | 15,000 | `testing` + `testify` | **20 d** |

**Total estimated effort, fluent engineer**: ~165 engineer-days (~33 working weeks ~= 8 months)
**Total estimated effort, learning-as-going**: ~250 engineer-days (~12 months at 5 days/week, ~36 weeks at 7 days/week)
**Realistic plan with summer course (15 hr/week)**: see `SUMMER_COURSE_PLAN.md` — first viable Go binaries shipped in week 4-6, full TUI by week 12, gateway port underway by month 4.

---

## 2. The "what to rewrite first" matrix

Order by (impact / effort), highest first:

| Rank | What | Why first | Effort |
|---|---|---|---:|
| 1 | `mercury-status` | Pure I/O, sub-day, gives Soumit a working Go binary on Day 1 of the course | 0.5 d |
| 2 | `mercury-watchdog` | Currently runs on Sera; replacing with a Go static binary lets us deploy to Pi too | 1 d |
| 3 | `mercury` CLI dispatcher | Entry point — wraps Python subcommands today; flipping to Go preserves all behavior, sets up the cobra structure | 1 d |
| 4 | TUI (Ink → Bubble Tea) | The one piece users SEE most. Going from React-on-Node to single-binary Bubble Tea is a UX jump (sub-100 ms cold start) | 20 d |
| 5 | `tui_gateway` (WS bridge for TUI) | Naturally pairs with the TUI rewrite | 4 d |
| 6 | Gateway (Discord adapter first) | Highest-traffic surface, Go's concurrency model genuinely wins here | 15-30 d |
| 7 | `mercury auth` | Concentrated complexity but blocks a lot — once done, all subsequent commands inherit | 5 d |
| 8 | `mercury sessions` + `mercury memory` | SQLite-backed; clean port; Go's typing helps a lot here | 6 d |
| 9 | `mercury cron`, `mercury hooks`, `mercury webhook` | Each ≤2 days, all share the same supervisor pattern as the gateway | 3 d |
| 10 | `mercury mcp` | Spec is tight, port is mechanical | 5 d |
| 11 | Tools (file_*, code_execution, delegate) | LLM-side; can stay Python for a long time | 9 d |
| 12 | Browser tool (chromedp) | High-value but high-risk; profile Patchright vs chromedp on actual Mercury workloads first | 8 d |
| 13 | LLM adapters (Anthropic, OpenAI, Gemini) | Big surface, lots of edge cases. SDKs exist; mostly translation work. Optional | 9 d |
| 14 | `run_agent.py` core | Last and biggest. Don't touch until everything else is settled. May not be worth it. | 15+ d |
| 15 | Web dashboard SPA | Pure UX work; HTMX rewrite is the cleanest path | 20 d |

---

## 3. Per-component design notes

### 3.1. `mercury-status` (the warmup)

Single Go file, ~80 LOC. Polls `http://localhost:8773/api/health` and the watchdog `http://localhost:8780/status`, prints colored output with `lipgloss`.

```
mercury-status
├── go.mod
├── main.go        # 50 LOC: parse flags, call render
├── render.go      # 30 LOC: lipgloss styles, table layout
└── README.md
```

Useful as the "hello world that does something Mercury actually needs".

### 3.2. `mercury` CLI dispatcher (the foundation)

Use `spf13/cobra` because it matches the argparse tree we have today. Each subcommand starts as `cmd.Run = func() { exec.Command("python", "-m", "mercury", "<sub>", args...) }` so we keep Python doing the work while we port commands one-by-one. As each subcommand goes Go-native, swap the `Run` body.

```
mercury-go/
├── go.mod
├── cmd/
│   └── mercury/
│       └── main.go             # cobra root + subcommand registration
├── internal/
│   ├── pyshim/                 # spawns Python subprocess for not-yet-ported subcommands
│   ├── status/                 # mercury status (Go-native)
│   ├── version/                # mercury version (Go-native)
│   └── ...
└── README.md
```

### 3.3. TUI (Ink → Bubble Tea)

Bubble Tea uses the **Elm architecture**: a Model holds state, an Update returns the next Model in response to messages, a View renders the Model to a string. This is React + Redux compressed into one idiomatic pattern, with no JS runtime.

Reference apps to study (all open source, all production):
- `gh` (GitHub CLI) — multi-screen TUI
- `glow` (Markdown reader)
- `lazygit` — interactive git client
- `k9s` — Kubernetes dashboard
- `charm.sh/freeze` — code screenshot tool

Mercury TUI surfaces to port:
- Chat view (split: messages above, prompt below)
- Session list
- Plugin status
- Live log tail (we have this in the cortex frontend; mirror the UX)
- Kanban board

Estimated 8K Go LOC for the entire TUI vs. 35K TypeScript today — Bubble Tea is dense.

### 3.4. Gateway

The pattern:

```go
type Platform interface {
    Name() string
    Start(ctx context.Context, msgs chan<- IncomingMessage) error
    Send(ctx context.Context, m OutgoingMessage) error
}

type Gateway struct {
    platforms []Platform
    agentRun  func(ctx context.Context, m IncomingMessage) (OutgoingMessage, error)
    log       *slog.Logger
}

func (g *Gateway) Run(ctx context.Context) error {
    msgs := make(chan IncomingMessage, 64)
    var wg sync.WaitGroup
    for _, p := range g.platforms {
        wg.Add(1)
        go func(p Platform) {
            defer wg.Done()
            if err := p.Start(ctx, msgs); err != nil {
                g.log.Error("platform failed", "platform", p.Name(), "err", err)
            }
        }(p)
    }
    
    for {
        select {
        case <-ctx.Done():
            wg.Wait()
            return ctx.Err()
        case m := <-msgs:
            go g.handleMessage(ctx, m)   // each message gets its own goroutine
        }
    }
}
```

Discord adapter: `bwmarrin/discordgo` is ~80% feature-complete vs. `discord.py`. Voice is partial — for voice features we still call out to Python. That's fine.

### 3.5. Agent loop (`run_agent.py`)

**Don't port this for at least 6 months**. The agent loop is where:
- LLM SDK semantics matter (Anthropic's exact streaming format, OpenAI's tool-call IDs, Gemini's part-array structure)
- Pydantic validates 50 message shapes
- Skills, hooks, plugins all hook in
- Tests are densest

Porting it = re-validating against every test. The Python version works. Lift only when the Go side is mature enough that the gateway can call into the Python agent core via subprocess + pipe (which we can do indefinitely).

### 3.6. Web dashboard

Two routes diverge:

**Path A: HTMX + Go templates (recommended)**
- ~30 KB total JS (just HTMX runtime)
- Server renders HTML; browser swaps fragments via `hx-get` / `hx-post` / `hx-swap-oob`
- Web Sockets for live updates via `hx-ws`
- Total Mercury rewrite size: ~2k Go LOC (templates + handlers)
- Zero npm, zero build step

**Path B: SolidJS (TypeScript stays)**
- ~7 KB runtime, much smaller than React's ~140 KB
- Reactive, fine-grained updates, faster than React
- Familiar JSX syntax for engineers from the React world
- Build pipeline: Vite stays, just swap react → solid

Recommendation: **HTMX**. Mercury's dashboard is mostly tables + forms + live log tails — the React reactivity layer was overkill. HTMX matches the actual interaction model.

### 3.7. Tools

Most file/process tools port mechanically — `os.Open` → `os.Open` (same name in Go!), `subprocess.run` → `os/exec.Command(...).Run()`. The tool that doesn't port mechanically is **browser**:

- `Patchright` (current) is a fork of Playwright with stealth patches. It's a Python wrapper around Node's Playwright runtime; using it means having Node + Chromium in the deploy.
- `chromedp/chromedp` (Go) is a pure Go DevTools client. It speaks CDP directly; no Node, no Playwright. ~50% feature parity with Playwright but covers Mercury's use cases (fetch page, screenshot, evaluate JS).
- The stealth patches don't transfer; if anti-bot is critical, keep Patchright on Python or evaluate a Go stealth fork (none currently mature).

Decision: **port to chromedp for the 80% case, leave Patchright as a fallback for stealth-required scrapes**.

---

## 4. Things that do NOT port well

These are the cliff edges. Worth naming so we don't burn cycles fighting them.

### 4.1. Discord voice

`discord.py` has full voice support (in-call audio, music bot, etc.). `discordgo` has partial voice support and the community has built scaffolding around it but it's noticeably less polished. If Mercury's Discord bot ever needs voice channels, keep that one feature in Python.

### 4.2. Pydantic-style validation

Pydantic v2 is in Rust under the hood and is very fast. Go's equivalent (`go-playground/validator`) does the right thing but the API is uglier — struct tags everywhere. For the LLM-bound message shapes that Pydantic guards in Mercury today, hand-rolled Go validation is clearer and equally fast. Just more verbose.

### 4.3. Jupyter / IPython

Doesn't exist in Go. Period. If Mercury ever wants to expose a notebook surface, Python stays.

### 4.4. Edge ML

Mercury doesn't run inference itself — it delegates to Ollama / OpenRouter / cloud. If we ever DO run inference (faster-whisper, sentence-transformers, etc.), Python stays for those bindings. Go can call them via subprocess.

### 4.5. RL / training

`environments/` has scaffolding for Atropos and Tinker (RL training). These are PyTorch + JAX ecosystems. Stay Python forever; not even a question.

### 4.6. The interactive Python REPL in Mercury

`cli.py`'s 11k LOC includes a prompt_toolkit-based interactive REPL with Python autocomplete, history search, and inline tool-call previews. Bubble Tea can replace the rendering, but the **completion engine** for any-Python-expression-the-user-types is Python. This is the single gnarliest port.

---

## 5. The hybrid steady state

After the rewrite that I'd actually recommend stopping at:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Mercury, hybrid future                        │
│                                                                    │
│  Go binaries (single-file, no runtime install):                  │
│   • mercury (CLI dispatcher)                                      │
│   • mercury-tui (Bubble Tea TUI)                                  │
│   • mercury-gateway (daemon, all platforms)                       │
│   • mercury-watchdog                                              │
│   • mercury-status                                                │
│                                                                    │
│  Python (still where it shines):                                 │
│   • agent/ core loop                                              │
│   • tools/ (browser, code exec, file ops)                        │
│   • LLM adapters (anthropic, openai, gemini)                     │
│   • mcp/ (server-side; client in Go)                             │
│   • plugins/                                                      │
│   • skills/ (markdown + python)                                  │
│                                                                    │
│  HTMX + Go templates (or SolidJS) for the dashboard SPA          │
│                                                                    │
│  How they talk:                                                  │
│   Go gateway → Python agent loop via                             │
│      json-rpc over Unix socket (or, simpler, subprocess + stdin) │
│   Go TUI → Mercury daemon via                                    │
│      Unix socket / WebSocket bridge                              │
│   Go CLI → Python core via                                       │
│      Just spawn `python -m mercury <cmd>` for not-yet-ported     │
└─────────────────────────────────────────────────────────────────┘
```

This shape:
- **Drops 60k LOC of TypeScript** (TUI + dashboard)
- **Drops ~15k LOC of Python** (CLI dispatcher + status + watchdog + gateway adapters)
- **Adds ~25k LOC of Go**
- **Net: ~50k fewer LOC, two fewer runtimes to install on a target node, sub-100 ms cold starts everywhere**

Time to that state at 15 hr/week (sustainable summer-course pace): **~9 months**.
Time at full-time engineer pace: **~3 months**.

---

## 6. The decision

Recommendation: **execute in priority order from §2**, ship every 2 weeks, **never** be in a state where Mercury is half-rewritten. Each Go binary plugs in as a drop-in replacement for the equivalent Python piece. If we run out of summer, the work doesn't unwind; we just stop with a partial hybrid that's still strictly better than today.

Don't rewrite the agent loop. Don't rewrite the LLM adapters unless we hit a Go-side wall that can't be bridged. Don't try to do this in a single PR.

---

## 7. Where this sits in the doc set

- `MERCURY_GO_WIKI.md` — the language itself (history, model, ecosystem)
- `LANGUAGE_COMPARISON.md` — Rust/Go/Python deeper analysis
- **`MERCURY_GO_REWRITE_ASSESSMENT.md`** — this doc (what to port, how, in what order)
- `SUMMER_COURSE_PLAN.md` — 12-week curriculum that pairs to this assessment
- `MERCURY_DIVERGENCE_PLAN.md` — the prior cherry-pick / rebrand plan (now mostly executed)
- `ARCHITECTURE_ANALYSIS.md` — why Mercury looks the way it does
