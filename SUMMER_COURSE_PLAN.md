# Summer Go Course — Mercury as the project

**Goal**: ship a working pure-Go Mercury subsystem (the TUI and CLI dispatcher, minimum) by the end of summer 2026, while learning Go from zero. The course is structured around **building Mercury components in order of impact / difficulty / wow-factor**, not around language features in the abstract.

**Hours**: 15 hr/week. ~3 evenings + Saturday morning. Sustainable.
**Duration**: 12 weeks (~Memorial Day → Labor Day).
**Companion docs**: `MERCURY_GO_WIKI.md` (the wiki), `MERCURY_GO_REWRITE_ASSESSMENT.md` (the port plan).

---

## 0. Setup (Week 0, before the course starts)

| Day | Task |
|---|---|
| Sun | Install Go (`winget install GoLang.Go`); verify `go version` |
| Mon | Install VS Code Go extension (auto-installs `gopls`, `dlv`, `golangci-lint`) |
| Tue | Open `https://go.dev/tour`, do welcome chapter |
| Wed | Read `MERCURY_GO_WIKI.md` end-to-end (saved in this repo) |
| Thu | Skim `knowledgebase/go-learn/blog_error-handling-and-go.html` and `gobyex_hello-world.html` |
| Fri | Type out + run the §7 ("first 100 lines") example from the wiki |
| Sat | Pick a `mercury-go/` repo location (e.g. `D:/mercury/mercury-go/`); `mkdir`; `go mod init github.com/AlexiosBluffMara/mercury-go` |

You're now ready for week 1.

---

## 1. Week 1 — Idioms (no Mercury yet)

**Theme**: think Go, write Go.

**Hours**:
- Mon (3 h): Tour chapters 1–3 (basics, control flow, types). Type out every example, don't copy.
- Tue (3 h): Tour chapters 4–6 (methods, interfaces, generics).
- Thu (3 h): Tour chapter 7 (concurrency). The Equivalent Binary Tree exercise — solve it.
- Sat (6 h): `effective_go.html` end-to-end. Make notes in a personal Markdown file.

**Deliverable**: a 100-line Go program that recursively walks a directory, prints filenames + sizes, sorted by size, with `--top=N` flag (use `flag` from stdlib, not `cobra` yet).

**Stretch**: same program with the size sort happening in a worker pool of goroutines. Doesn't matter — for this size of work goroutines hurt — but it teaches the pattern.

**Reading**: Go blog `errors-are-values` and `error-handling-and-go`.

---

## 2. Week 2 — Concurrency in anger

**Theme**: goroutines + channels are the language. Get fluent.

**Hours**:
- Mon (3 h): Replicate `gobyex_*` for goroutines, channels, select, timeouts, worker-pools, mutexes, atomic-counters, context. Each is short.
- Tue (3 h): Read Go blog `pipelines` (saved as `blog_pipelines` — wait, it's the pipelines blog). Implement an MD5 hasher pipeline: reads files from a chan, computes MD5, sends results to another chan. Cancel on ctrl-C with `signal.Notify` + `context`.
- Thu (3 h): Read `concurrency-is-not-parallelism`. Run your hasher with `GOMAXPROCS=1` then `GOMAXPROCS=8`. Time the difference.
- Sat (6 h): The `mercury-status` warmup — first real Mercury Go binary.

**Deliverable**: **`mercury-status`** — a Go binary that polls `cortex.redteamkitchen.com/api/fleet-health` every 2 s, displays:
- Both nodes' GPU usage (color-coded with `lipgloss`)
- The 5 services with status pills
- Recent scan list

Run it in a terminal and watch the display update. ~80 LOC.

**Reading**: Go blog `profiling-go-programs`. (You'll use this in week 8.)

---

## 3. Week 3 — Cobra and the CLI

**Theme**: you can't build Mercury without a CLI. Master cobra.

**Hours**:
- Mon (3 h): Install cobra-cli (`go install github.com/spf13/cobra-cli@latest`). Run `cobra-cli init` in `mercury-go/`. Skim what it generated. Read its docs.
- Tue (3 h): Implement two commands: `mercury status` (shells out to your Week 2 binary or duplicates the code) and `mercury version`.
- Thu (3 h): Implement `mercury config show` (reads `~/.mercury/config.yaml` with `yaml.v3`, pretty-prints with `lipgloss`).
- Sat (6 h): The Python compatibility shim. For every subcommand we haven't ported, the cobra `Run` body is `exec.Command("python", "-m", "mercury", cmdName, args...).Run()` so the Go binary can already be used as the entrypoint.

**Deliverable**: **`mercury-go`** — a single binary you can put in your PATH. Aliases over to Python for the unported commands. Works as a drop-in.

**Pragmatic test**: rename `mercury` (Python) to `mercury-py`, put `mercury-go` (Go) in PATH as `mercury`. Use it for daily work for a week. Notice the cold-start improvement (1.8 s → 80 ms).

---

## 4. Week 4 — TUI fundamentals (Bubble Tea hello world)

**Theme**: the Elm architecture. Model, Update, View.

**Hours**:
- Mon (3 h): Read the Bubble Tea README + tutorial. Implement the `tutorial-basics` example (cursor moves over a list with j/k, enter selects).
- Tue (3 h): Layer `lipgloss` on top — colored borders, padded boxes. Re-style your week-2 status display as a Bubble Tea app instead of plain `fmt.Println`.
- Thu (3 h): Read about commands (`tea.Cmd`). Add a tick command that polls fleet-health every 2 s and updates the model.
- Sat (6 h): Add a second view — pressing `g` swaps to a "gallery" view that hits `/api/scans?limit=20&status=all`. Press `b` to go back.

**Deliverable**: **`mercury-status` v2** — a Bubble Tea TUI with two screens, live updates, keyboard navigation. ~300 LOC.

This is the moment you realize Bubble Tea is FUN.

---

## 5. Week 5 — HTTP server foundations

**Theme**: stdlib `net/http`, JSON, structured logging.

**Hours**:
- Mon (3 h): `gobyex_http-server.html` and `http-client.html`. Implement an echo server.
- Tue (3 h): Add `slog` JSON logging on every request. Add `RequestID` middleware that generates a UUID and attaches to context.
- Thu (3 h): Read `blog_context.html`. Refactor your handlers to honor `r.Context()` for cancellation. Test by `curl --max-time 1` and confirming the server logs a cancelled request.
- Sat (6 h): Implement a tiny version of Mercury's `/api/fleet-health` endpoint in Go. Run it on port 8773 alongside the Python one (different port if 8773 conflicts). Compare RPS with `oha` or `ab`.

**Deliverable**: **`mercury-fleet-health-go`** — a Go HTTP server that serves the same JSON shape as Python's. Bench: should be 5-10× faster.

---

## 6. Week 6 — WebSockets

**Theme**: real-time, bidirectional, the most-asked-about Go pattern.

**Hours**:
- Mon (3 h): Read `coder/websocket` docs. Implement a server that echoes whatever the client sends.
- Tue (3 h): Build a fan-out hub: server has many clients, each `Send(message)` reaches all. This is exactly what Mercury's `WebSocketHub` does in `webapp/server.py`.
- Thu (3 h): Connect your Bubble Tea TUI from week 4 to a websocket on the server. Push updates via WS instead of polling. Watch the latency drop.
- Sat (6 h): Replace the polling in your week-2 `mercury-status` binary with the websocket-backed updates.

**Deliverable**: **TUI consuming websocket** — the start of the real Mercury TUI. Render frame in <50 ms when server pushes.

---

## 7. Week 7 — SQLite + sessions

**Theme**: the data layer. Mercury stores sessions, memories, credentials.

**Hours**:
- Mon (3 h): `modernc.org/sqlite` (pure Go SQLite, easier cross-compile than mattn). Implement `INSERT`, `SELECT`, `UPDATE`. Use `database/sql` interfaces.
- Tue (3 h): Schema for sessions: `id, started_at, ended_at, model, message_count`. Implement `mercury sessions list` (Go-native).
- Thu (3 h): FTS5 for session content search. Implement `mercury sessions search "query"`.
- Sat (6 h): Read Mercury's existing `sessions/` Python code in detail. Write Go to read the SAME schema (DON'T duplicate the data). Both Go and Python now read from `~/.mercury/sessions.db`.

**Deliverable**: **`mercury sessions {list,search}`** — Go-native, no Python shim. Sub-50 ms response on 10k sessions.

---

## 8. Week 8 — Profiling and benchmarks

**Theme**: measure, don't guess.

**Hours**:
- Mon (3 h): Read `blog_profiling-go-programs.html`. Add `import _ "net/http/pprof"` to your fleet-health server. Hit `/debug/pprof/`. Generate a CPU profile under load.
- Tue (3 h): Write benchmarks for your week-7 SQLite session search using `func BenchmarkSessionSearch(b *testing.B)`. Run with `go test -bench=. -benchmem`.
- Thu (3 h): Race detector. Build your fleet-health server with `go build -race`. Hit it with concurrent requests. Find any data races.
- Sat (6 h): Profile-guided optimization. Generate profiles from a real workload, recompile with `-pgo=default.pgo`. Compare numbers.

**Deliverable**: **A benchmarks file** in `mercury-go/internal/sessions/sessions_bench_test.go` that proves your Go code is 5-10× faster than Mercury's Python equivalent on the same SQLite database.

---

## 9. Week 9 — Discord adapter (Go gateway begins)

**Theme**: rewrite the highest-traffic surface. `discordgo` + goroutine-per-channel pattern.

**Hours**:
- Mon (3 h): Read `discordgo` README. Get a bot token. Hello-world bot that echoes every message.
- Tue (3 h): Implement the same logic as Mercury's `gateway/platforms/discord.py`'s message handler. Same channel allowlist, same message deduplication.
- Thu (3 h): Hook your Discord bot to call into Mercury's Python agent core via subprocess for now (`exec.Command("python", "-m", "mercury", "chat", "-z", message).Output()`). The Go side handles the Discord shape; Python does the LLM call.
- Sat (6 h): Compare resource usage: Python `gateway/run.py` vs your Go bot, both running 10 minutes against the same channel. Memory, CPU, latency.

**Deliverable**: **`mercury-gateway-discord-go`** — a small Go binary that owns the Discord connection. Runs alongside the Python gateway during the transition.

---

## 10. Week 10 — Plugin loader (IPC)

**Theme**: the architectural challenge. How does the Go core talk to Python plugins?

**Hours**:
- Mon (3 h): Design exercise. Write a 1-page doc on protocol options (JSON-RPC over stdio vs Unix socket vs gRPC vs shared library). Pick one, justify.
- Tue (3 h): Implement the chosen protocol. If JSON-RPC over stdio: server spawns `python plugin.py`, sends requests on stdin, reads responses on stdout. ~150 LOC each side.
- Thu (3 h): Run a Mercury skill from your Go gateway via the new IPC. Time it.
- Sat (6 h): Add capability declarations: each plugin announces "I can handle X event types"; Go gateway routes by type.

**Deliverable**: **`mercury plugins run <name>`** in Go that can invoke any existing Python plugin. Foundational for everything that follows.

---

## 11. Week 11 — Cross-compile + deploy

**Theme**: the Go advantage. Single binary, anywhere.

**Hours**:
- Mon (3 h): `GOOS=linux GOARCH=arm64 go build -o mercury-status-pi ./cmd/mercury-status`. Copy to Baby Pi via Tailscale. Run it. Time the cold start.
- Tue (3 h): Same for `mercury-gateway-discord-go`. Run on the Pi as a systemd unit.
- Thu (3 h): Set up a GitHub Actions workflow that builds for `linux/amd64`, `linux/arm64`, `darwin/arm64`, `windows/amd64` on every push.
- Sat (6 h): Embed assets (HTML, CSS, JS) into the binary with `embed.FS`. Now your Go web server is one file.

**Deliverable**: a release pipeline that produces a downloadable `mercury` binary for every node. Pi gets ARM64. Mac gets darwin/arm64. Sera gets windows/amd64.

---

## 12. Week 12 — Polish and consolidate

**Theme**: ship.

**Hours**:
- Mon (3 h): Go through your code with `golangci-lint run` (it bundles ~50 linters). Fix everything.
- Tue (3 h): Add `--help` text to every cobra command. Use `https://nitter.net/manpages` style.
- Thu (3 h): Write a README for `mercury-go/` that explains how to build, what's ported, what's not.
- Sat (6 h): Demo. Record a 5-min screencast showing the Go components running. Post in Discord.

**Deliverable**: a v0.1 of `mercury-go` that REPLACES the following Python pieces in production:
- `mercury status`
- `mercury sessions list/search`
- `mercury-status-tui` (the Bubble Tea app)
- `mercury-gateway-discord` (running side-by-side with Python gateway, can flip)
- `mercury-watchdog`

---

## What you'll have learned

By Labor Day, you can:
- **Read any open-source Go project** (CockroachDB source, Prometheus source, Tailscale source).
- **Write idiomatic Go code** that passes `golangci-lint` clean.
- **Profile and optimize** Go programs with `pprof`.
- **Cross-compile and deploy** Go binaries to any of three architectures.
- **Use channels and goroutines** for concurrent work without deadlocking.
- **Build TUIs** with Bubble Tea that feel native.
- **Build CLIs** with cobra that feel like `gh`, `kubectl`, `docker`.
- **Build HTTP services** with `net/http` that handle 10k req/s on a Pi.
- **Use the race detector** to catch concurrency bugs at test time.

This is **mid-level Go engineer** territory after 12 weeks of part-time learning. Three more months at the same pace gets you to senior.

---

## Resume bullet, drafted

> **2026 — Pure-Go rewrite of Mercury (open source agent platform).** Self-taught Go from zero over a 12-week summer course. Shipped 5 production Go components replacing Python equivalents: a Bubble Tea TUI (8K LOC, sub-100ms cold start vs 1.8s Python), a Discord gateway (5x lower memory, 6x higher message throughput), a fleet watchdog, a session/memory store backed by SQLite, and the unified CLI dispatcher. Stack: Go 1.24 + Bubble Tea + cobra + discordgo + chromedp + modernc.org/sqlite. Repo: github.com/AlexiosBluffMara/mercury (mercury-go/ subdir).

That's a real bullet. It's specific, technical, and proves both the language acquisition AND the engineering judgement (knew which pieces to port, kept what worked).

---

## Beyond week 12 (autumn semester)

Optional next-quarter targets:
- **Web dashboard rewrite** (HTMX + Go templates, ~20 days of work)
- **MCP client + server** in Go (~5 days)
- **Auth providers** (OAuth flows for Anthropic, OpenAI, Google) (~5 days)
- **Cron + hooks + webhooks** (~3 days, naturally pairs with the gateway)

This is also a natural point to **refactor the Python agent loop** if a port still feels worth it (probably not — it works well).

---

## Course rules (because plans need them)

1. **Ship every 2 weeks**, no exceptions. Even if it's 80 LOC, push it.
2. **No language wars**. Go is what we're learning. Python comparisons are for context, not for re-litigating choices.
3. **Read the source** of any Go library before you depend on it. They're all small enough.
4. **Read your own code aloud** before committing. Go is verbose; verbose readable beats clever opaque.
5. **`golangci-lint run` is the code review gate**. Lint passes or it doesn't merge.
6. **Tests for everything new**. Aim for 70% coverage; reach for 90% on the components that touch other systems.
7. **One PR per concern**. Don't slip a refactor into a feature commit.
8. **The Pi is the deployment validator**. If it doesn't run on Baby Pi (ARM64 Linux), it's not finished.

---

## What this course will NOT teach

- Frontend Go (TinyGo + WASM is real but niche; not on the path)
- Heavy generics (we'll touch them but Go's standard idiom is "use interfaces unless you have to")
- The Go runtime internals (we'll respect them, not modify them)
- Game dev / graphics in Go (Ebiten exists but it's not Mercury-shaped)
- Embedded Go (the Pi is the embedded target; that's enough)

---

## Final thought

Mercury is a 244K-LOC Python+TS codebase. We're not rewriting all of it. We're carving off the parts where Go's strengths (cold start, single binary, concurrency model, deployability, smaller resource footprint) make a real difference, leaving the agent core in Python where the LLM SDK ecosystem lives. The course is the way to get fluent enough to do that judiciously.

12 weeks. 15 hr/week. Single binary at the end. Ship it.
