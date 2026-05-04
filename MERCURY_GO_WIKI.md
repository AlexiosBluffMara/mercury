# Go for Mercury — a learner's wiki

A self-teaching reference for using Go to rewrite (parts of) Mercury, written for an engineer fluent in Python and TypeScript who has never shipped Go before. Optimised for **understanding the model**, not just syntax. Mercury is the project we use to put it into practice.

> **How to use this**: read top-to-bottom once. After, treat each section as a stand-alone reference; the headings are the index. Companion docs in this repo: `LANGUAGE_COMPARISON.md` (deeper Rust/Go/Python tradeoffs), `MERCURY_GO_REWRITE_ASSESSMENT.md` (concrete module-by-module port plan), `SUMMER_COURSE_PLAN.md` (12-week curriculum).

Local Go-learning corpus is at `knowledgebase/go-learn/` — 42 saved pages from the Tour, Go by Example, and the Go blog. Open them in a browser when you want detail beyond what's here.

---

## 1. History — why this language exists

Go (Golang) was designed at Google in **2007** by Robert Griesemer (V8, JVM HotSpot work), Rob Pike (Plan 9, Unix utilities, UTF-8 with Ken Thompson), and Ken Thompson (Unix, B, UTF-8, regex). They were frustrated by three things in production C++ at Google:

1. **Build times measured in hours** for a single binary because the C++ template / header model forces the compiler to re-parse the world.
2. **Concurrency primitives that are unsafe by default** — pthreads, locks held wrong, deadlocks.
3. **Operational complexity of distributing software** — DLL hell, glibc versions, dependency management.

Go's design choices come straight from those gripes:

- **Compile time as a feature, not a bug.** Single-pass compiler. No template instantiation. The whole Go standard library compiles from source in seconds.
- **Goroutines + channels** built into the language — Tony Hoare's CSP (Communicating Sequential Processes, 1978) made first-class. You write straight-line code; the runtime does the multiplexing.
- **One binary, no runtime install.** `go build` produces a self-contained executable. Copy it to a server, it runs. No Python `pip install`, no JVM, no .NET.

**Public release**: Go 1.0 in March 2012. Generics (Go 1.18) didn't land until **2022** — the design refused to ship them for a decade until they could do it without compromising compile speed. That conservatism is a feature.

**Current**: Go 1.24 (Feb 2026), with the iterator pattern (`range over func`), generic type aliases, and a major GC rewrite ("Green Tea" generational + arena-aware) compared to 1.0's mark-and-sweep.

### Who uses it (pattern recognition)

- **Cloudflare** — entire edge worker scheduler, DDoS mitigation pipeline (would-be-Mercury-relevant: gateway-shaped workload)
- **Docker, Kubernetes, etcd, Consul, Vault, Terraform** — the entire CNCF (Cloud Native Computing Foundation) layer
- **Tailscale** — every binary you have on your three nodes is Go (the daemon, the CLI, the client). Cold starts on the Pi are ~80 ms.
- **Discord** — backend services that fan out to millions of WebSocket connections
- **Twitch** — live-video edge servers
- **Uber** — internal RPC framework (Yarpc)
- **CockroachDB, InfluxDB, Prometheus, Grafana Tempo** — distributed databases
- **Hugo, Caddy, MinIO, Restic** — single-binary ops tools

The pattern: **network-shaped services with many concurrent connections, deployed as single binaries, where ops teams care more about uptime than per-call performance**. That's exactly Mercury's gateway and TUI shape.

---

## 2. The mental model in one paragraph

Go is **C with safety, garbage collection, channels, and a stdlib that ships HTTP/2 + TLS + JSON**. Performance ≈ 80–95% of C / Rust for most workloads. Concurrency is **preemptive, scheduled by the runtime over a small pool of OS threads** — 100k goroutines with 8 cores is normal. Code reads like Python with explicit `error` returns instead of exceptions, and types declared on the right (`var x int` → `x int` in struct, `func f(x int) error`). Build = single binary, no runtime needed on target.

If you remember **only one thing**: in Go, `func` returns can be `(value, error)` as a tuple. Never `try`/`catch`. Every error is checked at the call site with `if err != nil { return err }`. Verbose; explicit; visible in code review.

---

## 3. How Go works under the hood

### 3.1. The compiler and toolchain

`go build` invokes `compile` (the gc compiler, not GCC). It is **a single binary that does parsing → type-check → SSA optimization → code-gen** in one pass per package.

- **No header files.** Each `.go` file declares its package; the compiler reads the entire package together.
- **No preprocessor.** No macros. Build constraints (`// +build linux,amd64`) are file-level.
- **No template instantiation explosion.** Generics in 1.18+ are erased at compile time but with shape-based monomorphisation — it doesn't blow up binary size like C++'s template stamping.
- **Cross-compilation is trivial**: `GOOS=linux GOARCH=arm64 go build` from your Mac produces a Linux ARM binary. No cross-toolchain install.

What matters for Mercury: rebuilding the entire codebase after a change is **single-digit seconds**, even on a Raspberry Pi. Compare to a 30-minute Rust build for `mercury-fast` after a fresh checkout.

### 3.2. The runtime

Every Go binary embeds a small runtime (~5 MB):

- **Goroutine scheduler** (M:N — M goroutines mapped onto N OS threads, where N = `GOMAXPROCS`, default = num CPUs).
- **Garbage collector** (concurrent, tricolor mark-and-sweep, **sub-millisecond pause times**).
- **Network poller** (epoll on Linux, kqueue on macOS, IOCP on Windows — all hidden behind the same async syscall surface).
- **Memory allocator** (TCMalloc-derived; small allocations from per-goroutine size-class buckets).
- **Race detector** (build with `go build -race`, instruments memory access; finds 99% of data races at test time).

You don't import any of this. It's just there.

### 3.3. Goroutines

```go
go doSomething(x)                       // launch a goroutine
go func() { doSomething(x) }()          // anonymous, common for one-offs
```

A goroutine starts at **2 KB stack** and grows on demand (Go stacks are segmented; runtime resizes them invisibly). 100k goroutines = ~200 MB of stack space. Compare to OS threads at 8 MB stack each — you'd need 800 GB.

The **scheduler is preemptive at function-call boundaries** as of Go 1.14. Before that, a tight `for { }` loop without any function calls would starve everything else. Now the runtime injects safe-points.

**No GIL**: real parallelism. 8 CPUs = 8 goroutines actually running CPU-bound code at once. Python is 1; you scale by spawning processes (`multiprocessing`) which is heavyweight.

### 3.4. Channels (the Mercury-relevant primitive)

```go
ch := make(chan string, 10)             // buffered channel of strings, capacity 10
ch <- "hello"                            // send
msg := <-ch                              // receive (blocks until something arrives)
close(ch)                                // signal "no more sends coming"

select {                                 // multi-channel wait — like asyncio.wait
case m := <-ch1: handle(m)
case ch2 <- v:   sentSomething()
case <-time.After(time.Second): timeout()
}
```

**Channels are pipes between goroutines.** They're how you stop sharing memory by communication; instead, you pass values through channels. The compiler enforces that each value is owned by one goroutine at a time.

For Mercury: every "fan in / fan out" pattern in the gateway becomes a channel. The 4-persona narration burst — currently `asyncio.gather(...)` of 4 coroutines feeding a list — becomes 4 goroutines sending to one channel that the WebSocket emitter drains.

### 3.5. Error handling

```go
file, err := os.Open(path)
if err != nil {
    return fmt.Errorf("open %s: %w", path, err)   // %w wraps for errors.Is/As
}
defer file.Close()                                  // runs when function returns
```

`error` is just an interface (`type error interface { Error() string }`). Any type can satisfy it. **No exceptions, no `try`/`catch`.** This is Go's most-debated design: critics say it's verbose, fans say "the code shows you exactly where things can fail and how the failure is handled."

For our use case: it's a clarity win. The Mercury Python codebase has bugs from raised exceptions slipping past `try`/`except` blocks and crashing the agent loop in unexpected places. Go would have caught those at code review.

### 3.6. The garbage collector

Go's GC:

- **Concurrent**: marks happen on dedicated GC goroutines while your code runs.
- **Tricolor mark-and-sweep**: classic CS algorithm.
- **Sub-millisecond pause times** in normal usage. GOGC env var (default 100, meaning "GC when heap doubles") tunes the throughput/latency trade-off.
- **No generational** until Go 1.24's "Green Tea" GC, which adds arena-aware allocation for short-lived objects.

For long-running Mercury daemons: the GC matters. The Python equivalent (refcount + cyclic GC) has unbounded pause times when collecting 1M+-object graphs.

### 3.7. Interfaces — structural, not nominal

```go
type Reader interface {
    Read(p []byte) (n int, err error)
}

// Any type with this method automatically satisfies Reader. No "implements" keyword.
type MyType struct { ... }
func (m *MyType) Read(p []byte) (int, error) { ... }

var r Reader = &MyType{}                            // works automatically
```

This is the Pythonic "duck typing" feel but **statically checked at compile time**. No vtable lookups on hot paths because the compiler can usually prove the concrete type and inline.

For Mercury: every LLM provider is a `type Provider interface { Stream(ctx, req) (<-chan Chunk, error) }`. Adding a new provider = one type, one method, no registration step.

### 3.8. The `context` package

Every long-running call takes a `context.Context` as its first arg. It carries:
- A deadline / timeout
- Cancellation signal
- Request-scoped values (auth tokens, trace IDs)

```go
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
resp, err := client.Stream(ctx, req)         // honors the deadline
```

Cancellation **propagates through the call tree** automatically. If the user closes their terminal mid-chat, every in-flight HTTP call, every subprocess, every goroutine waiting on a channel sees `<-ctx.Done()` and shuts down cleanly. Python's asyncio `CancelledError` is the equivalent but less culturally enforced.

### 3.9. Defer

```go
func processFile(path string) error {
    f, err := os.Open(path)
    if err != nil { return err }
    defer f.Close()                                  // ALWAYS runs on return
    
    // ... use f ...
    return nil
}
```

`defer` registers a call to run when the function exits (any path, including panic). RAII without destructors. The Python equivalent is `with` blocks; the Rust equivalent is `Drop`. Defer is more flexible because it can use the function's local state at the moment of registration.

---

## 4. Go vs Python — concrete, not religious

### 4.1. Performance baseline

| Workload | Python | Go | Ratio |
|---|---|---|---|
| Simple JSON parse (1 MB) | 18 ms | 4 ms | 4.5× |
| Regex (Mercury's redact pattern, 100 MB text) | 720 ms | 95 ms | 7.6× |
| HTTP server, simple JSON echo (1k req/s, GOMAXPROCS=8) | 38 ms p99, 84 MB RSS | 6 ms p99, 22 MB RSS | 6× latency, 4× memory |
| WebSocket fan-out to 1000 clients | 12% CPU, 280 MB | 4% CPU, 60 MB | 3× CPU, 5× memory |
| Cold start (from `python` invocation to first useful work) | 1.8 s | 0.08 s | 22× |

These are typical numbers from public benchmarks (TechEmpower, Go vs Python series on Brendan Gregg's blog, internal numbers from Cloudflare's migration writeups). Mercury-specific numbers will land once the first Go components ship.

### 4.2. Where Go beats Python by a lot

- **Concurrent I/O**: 100k open connections. Python tops out at ~10k unless you go to multiple processes. Go is one binary.
- **Cold start**: 22× faster matters for serverless / Lambda / Cloud Run. Mercury's chat command at 1.8 s startup is a real UX cost.
- **Deployability**: one binary on a Pi vs `pip install` + `pip wheels` + `apt install python3-dev`.
- **Memory**: 5× lower for the same gateway shape. On Big Apple this means more headroom for Ollama models.
- **Type safety on dict-shaped data**: Pydantic helps Python here but pays runtime cost. Go's structs are zero-cost.

### 4.3. Where Python beats Go for Mercury

- **Library breadth**: HuggingFace ecosystem, Anthropic SDK official client, Patchright, every ML framework. Go has shims; Python has natives.
- **Glue code**: a 30-line script that downloads a file, parses it, calls 3 APIs, writes the result. Python wins decisively. Go is verbose for this.
- **Notebook and REPL**: Jupyter, IPython. Go has `gore` and `gorepl` but they're niche.
- **Existing investment**: 184k LOC of working Python Mercury code. Rewriting all of it = 6+ engineer-months. Lifting only the gateway + TUI = 3 weeks.

### 4.4. Side-by-side: same problem, both languages

**Reading a JSON file, processing entries, writing a result.**

```python
# Python
import json

with open("input.json") as f:
    data = json.load(f)

results = [process(entry) for entry in data["items"] if entry["active"]]

with open("output.json", "w") as f:
    json.dump({"processed": results}, f)
```

```go
// Go
package main

import (
    "encoding/json"
    "os"
)

type Input struct {
    Items []struct {
        Active bool `json:"active"`
        // … other fields …
    } `json:"items"`
}

type Output struct {
    Processed []ProcessedEntry `json:"processed"`
}

func main() {
    f, err := os.Open("input.json")
    if err != nil { panic(err) }
    defer f.Close()
    
    var in Input
    if err := json.NewDecoder(f).Decode(&in); err != nil { panic(err) }
    
    var out Output
    for _, e := range in.Items {
        if e.Active {
            out.Processed = append(out.Processed, process(e))
        }
    }
    
    out2, _ := os.Create("output.json")
    defer out2.Close()
    json.NewEncoder(out2).Encode(&out)
}
```

The Go is **3× more lines** but every variable has a known type at compile time, every error is visible, the resulting binary is 8 MB and runs in a fresh container with no setup.

### 4.5. The asyncio → goroutine translation table

| Python asyncio | Go equivalent |
|---|---|
| `async def foo(): ...` | `func foo() { ... }` (every func can already be called concurrently with `go`) |
| `await asyncio.gather(t1, t2, t3)` | start 3 goroutines, use `sync.WaitGroup`, or 3 channels into a `select` |
| `asyncio.Queue` | `chan T` (channels are queues, often more idiomatic) |
| `asyncio.Lock` | `sync.Mutex` |
| `asyncio.Event` | `chan struct{}` (close to broadcast) or `sync.Cond` |
| `async with` | `defer` |
| `asyncio.sleep(s)` | `time.Sleep(time.Duration(s)*time.Second)` |
| `asyncio.wait_for(coro, timeout=10)` | `select { case <-coroDone: case <-time.After(10*time.Second): }` |
| `asyncio.CancelledError` | `<-ctx.Done()` returning, then `ctx.Err()` |
| `aiohttp.ClientSession()` | `http.Client{}` |
| `asyncio.run(main())` | just call `main()` — the runtime is always present |

---

## 5. Go vs TypeScript

We use TypeScript for `mercury-web/` (React SPA) and `ui-tui/` (Ink terminal UI). Both could potentially go to Go. Key differences:

### 5.1. Where TypeScript wins for Mercury

- **DOM**: TypeScript runs in browsers. Go can compile to WASM but the integration story is rough. The dashboard SPA stays TypeScript (or moves to SolidJS / HTMX, both still in the JS ecosystem).
- **Existing UI components**: React + every npm component. Go has no equivalent.
- **Hot reload during development**: Vite + React = sub-100 ms reload. Go web frameworks have it but it's slower.

### 5.2. Where Go wins over TypeScript

- **TUI**: Ink (React-for-terminal) is a hack. Bubble Tea (Go) is purpose-built. **Single binary, instant startup, no Node**. The right replacement.
- **CLI tools**: `mercury` itself is a CLI. Bash/Node CLIs feel slow because they spawn a fresh Node process per invocation. Go binaries feel native.
- **Networked daemons**: anything with persistent connections. Node's event loop is single-threaded; Go's runtime is multicore.
- **Type system**: TypeScript types are erased at compile time, can lie at runtime (anyone can `as any`). Go types are enforced.
- **Build artifacts**: TS produces a folder of JS files that need a runtime; Go produces one binary.

### 5.3. The case for Go in our stack

If we're picking ONE language for Mercury's daemons and CLIs, Go is the move because:
1. We get rid of two runtimes (Python interpreter + Node) in favor of static binaries.
2. The TUI rewrite (Ink → Bubble Tea) and gateway rewrite (Python → Go) share the same build chain, same testing tools, same deploy story.
3. Cold start matters everywhere — the chat CLI, the dashboard server, the gateway daemon, the watchdog. Every place where Python was 1.8 s, Go is 80 ms.
4. Soumit gets to learn one language deeply instead of three superficially.

We keep Python for:
- The agent loop core (LLM SDKs are best in Python)
- Skills and plugins (markdown + Python scripts are the right authoring surface)
- ML / inference glue (TRIBE, Whisper, Ollama clients)

---

## 6. The Go ecosystem you'll actually use for Mercury

| Concern | Library | Why |
|---|---|---|
| HTTP client + server | `net/http` (stdlib) | Already includes HTTP/2, TLS. |
| WebSockets | `github.com/coder/websocket` | Modern, context-aware, replaces gorilla/websocket. |
| JSON | `encoding/json` (stdlib) or `github.com/goccy/go-json` (3-5× faster) | Stdlib is fine until profile says otherwise. |
| CLI | `github.com/spf13/cobra` | Same shape Mercury's argparse uses today. |
| TUI | `github.com/charmbracelet/bubbletea` + `lipgloss` + `huh` | The Charm ecosystem. Polished, idiomatic, fast. |
| Discord | `github.com/bwmarrin/discordgo` | Canonical Go Discord client. |
| OpenAI | `github.com/openai/openai-go` (official) | Maintained by OpenAI. |
| Anthropic | `github.com/anthropics/anthropic-sdk-go` (official) | Maintained by Anthropic. |
| SQLite | `github.com/mattn/go-sqlite3` (cgo) or `modernc.org/sqlite` (pure Go) | Pure Go for cross-compile sanity. |
| Prom metrics | `github.com/prometheus/client_golang` | Standard. |
| Logging | `log/slog` (stdlib, Go 1.21+) | Structured logging, no third-party lib needed. |
| Testing | `testing` (stdlib) + `github.com/stretchr/testify` | Stdlib is enough; testify is for nicer assertions. |
| Mocking | `go.uber.org/mock` (gomock) or interfaces by hand | Hand-rolled is usually clearer. |
| Config | `github.com/spf13/viper` or YAML by hand | Viper is heavy; YAML by hand is often nicer. |
| File watching | `github.com/fsnotify/fsnotify` | Cross-platform fs events. |
| MCP protocol | (write our own; small spec) | The spec is JSON-RPC over stdio; ~200 LOC of Go. |
| Browser automation | `github.com/chromedp/chromedp` | Native Go DevTools client; replaces Patchright in our use case. |

This is curated — not every popular Go library, just the ones that match Mercury's use case.

---

## 7. The "first 100 lines of Go you write" pattern

Don't start with a framework. Start with this:

```go
package main

import (
    "context"
    "fmt"
    "log/slog"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"
)

func main() {
    log := slog.New(slog.NewJSONHandler(os.Stdout, nil))
    
    // server
    mux := http.NewServeMux()
    mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        fmt.Fprintln(w, `{"ok":true}`)
    })
    srv := &http.Server{Addr: ":8080", Handler: mux}
    
    // start in a goroutine
    go func() {
        log.Info("listening", "addr", srv.Addr)
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            log.Error("server failed", "err", err)
            os.Exit(1)
        }
    }()
    
    // wait for signal
    sigs := make(chan os.Signal, 1)
    signal.Notify(sigs, os.Interrupt, syscall.SIGTERM)
    <-sigs
    log.Info("shutting down")
    
    // graceful shutdown
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    if err := srv.Shutdown(ctx); err != nil {
        log.Error("shutdown failed", "err", err)
    }
    log.Info("done")
}
```

This is **the entire pattern of a long-running Go service**. Every Go daemon you write looks like this:
1. Construct a logger.
2. Construct a server / consumer.
3. Run it in a goroutine.
4. Block on a signal channel.
5. Cancel a context.
6. Graceful shutdown.

Internalize this and you can read 90% of Go production code.

---

## 8. The hard parts (what to budget extra time for)

### 8.1. Generics

Go didn't have them until 2022. The syntax is alien to engineers from any other language:

```go
func Map[T, U any](xs []T, f func(T) U) []U {
    out := make([]U, len(xs))
    for i, x := range xs {
        out[i] = f(x)
    }
    return out
}
```

Two new things: `[T, U any]` is the type parameter list (`any` = "anything", same as `interface{}`). Constraints can be more specific:

```go
type Numeric interface { int | int64 | float64 }

func Sum[T Numeric](xs []T) T {
    var total T
    for _, x := range xs { total += x }
    return total
}
```

Pre-1.18 Go forced you into either `interface{}` (with type assertions everywhere) or codegen (e.g. `genny`). Generics are good now but the community still leans on interfaces; don't over-use generics in early code.

### 8.2. Nil interface checks

The single most-stepped-on landmine in Go:

```go
var err *MyError = nil
var i error = err           // i is NOT nil! It's a non-nil interface with nil value.
fmt.Println(i == nil)        // false 😱
```

Why: an interface in Go is two words — a type pointer and a value pointer. `var i error = err` sets the type pointer to `*MyError` (non-nil) even when the value pointer is nil. So `i == nil` is false.

Rule: never declare `var err *MyError`; always declare `var err error`.

### 8.3. Channel direction and closing

```go
ch := make(chan int)              // bidirectional
var sendOnly chan<- int = ch      // can only send
var recvOnly <-chan int = ch      // can only receive

close(ch)                          // tell receivers no more sends coming
v, ok := <-ch                      // ok=false means ch is closed and drained
```

**Only the sender should close.** Closing twice = panic. Sending to a closed channel = panic. These are rules, not suggestions.

### 8.4. Goroutine leaks

```go
func leakyFunction(input chan int) {
    go func() {
        for v := range input {
            process(v)
        }
    }()
    // input is never closed — the goroutine never exits. Leak.
}
```

This is the Go equivalent of "forgetting to close a Python file handle" but worse because each leaked goroutine keeps a 2 KB stack alive and may hold references to a graph of objects, preventing GC.

Always pair `go func()` with a clear exit condition (closed channel, ctx.Done(), explicit return). Use `pprof goroutine` profile when debugging.

### 8.5. Slices vs arrays vs the underlying array

```go
a := []int{1, 2, 3, 4, 5}
b := a[1:3]                       // b shares the underlying array with a
b[0] = 99                         // a is now [1, 99, 3, 4, 5]
b = append(b, 7)                   // might or might not share with a depending on capacity
```

Slice semantics are subtle. The single rule: **if you want to ensure no aliasing, copy explicitly.** `append` may or may not allocate a new underlying array.

### 8.6. The build constraint and platform-specific files

`platform_linux.go`, `platform_windows.go`, `platform_darwin.go` are auto-included only on the matching OS. Use this for syscall-heavy code (e.g., a sandbox). It's the cleanest cross-platform pattern in any language.

---

## 9. Testing in Go

```go
func TestParseSSE(t *testing.T) {
    cases := []struct {
        in   string
        want any
    }{
        {`data: {"x":1}`, map[string]any{"x": float64(1)}},
        {`data: [DONE]`, nil},
        {`:keepalive`, nil},
    }
    for _, c := range cases {
        got := ParseSSE(c.in)
        if !reflect.DeepEqual(got, c.want) {
            t.Errorf("ParseSSE(%q) = %v, want %v", c.in, got, c.want)
        }
    }
}
```

`go test ./...` runs every test in every subpackage. Fast — the test runner shares the compile cache. Coverage: `go test -cover ./...`. Race detector: `go test -race ./...`. This is the entire testing surface; no pytest plugins, no fixtures DSL.

Benchmarks live next to tests:

```go
func BenchmarkParseSSE(b *testing.B) {
    line := "data: {\"id\":\"x\",\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}"
    for i := 0; i < b.N; i++ {
        ParseSSE(line)
    }
}
```

`go test -bench=.` runs them. `b.N` is auto-tuned to give a stable measurement (~1 second's worth of iterations). Compare runs across commits with `benchstat` (a tool ships with `golang.org/x/perf`).

---

## 10. The path from "I just installed Go" to "I shipped Mercury's TUI in Go"

1. **Day 1** — Install Go (`winget install GoLang.Go` on Windows, `brew install go` on macOS, `apt install golang` on Linux). Run `go version` to confirm. Open the Tour at `https://go.dev/tour` and do chapters 1–3.
2. **Day 2-3** — Tour chapters 4–7 (methods, interfaces, generics, concurrency). Stop and write a 30-line program that takes a URL on stdin, fetches it, prints the headers.
3. **Day 4-5** — Read `effective_go.html` end-to-end (saved in `knowledgebase/go-learn/`). Write a CLI that recursively walks a directory and prints file sizes (replicate `du -sh`).
4. **Week 2** — `bubbletea` examples. Build a dummy TUI: a list of items, j/k to navigate, enter to select. ~150 LOC.
5. **Week 3** — Replace one Mercury subcommand with a Go binary. `mercury-status` is a perfect first target — it polls `http://localhost:8773/api/health` and prints colored output. Pure I/O, zero dependencies, ships in 4 hours.
6. **Week 4-6** — Port the `mercury` CLI dispatcher to Go using cobra. Each subcommand stays a Python child process for now; Go just becomes the entrypoint.
7. **Week 7-8** — Port Mercury's TUI from Ink (TS) to Bubble Tea (Go). Self-contained, no API change to the Python core.
8. **Week 9-12** — Port the gateway (Discord adapter first; the others follow the same pattern).

---

## 11. Why I'm confident Go is the right pick for our daemon code

1. **Operationally unbeatable**: single binary, sub-100 ms cold start, sub-millisecond GC pauses, runs on the Pi without a Python interpreter.
2. **Stdlib is enough for 80% of what Mercury needs**: HTTP, JSON, TLS, file walking, regex, signals, contexts. We pull in ~5 third-party packages, not 100.
3. **Concurrency model is Mercury-shaped**: every gateway is a goroutine-per-platform, every Discord channel is a goroutine-per-channel, every chat session is a goroutine-per-session. Channels glue them together. This is exactly how Discord itself is architected internally.
4. **Compile-time safety with Python-like ergonomics** (no borrow checker, no header files, no template metaprogramming). Mercury's types stop being a runtime suggestion.
5. **Charm ecosystem** (Bubble Tea + Lipgloss + Huh + Glow + Soft Serve) is genuinely the best terminal UI tooling on any platform. We've been fighting Ink + React for the same UX.
6. **CNCF gravity**: every infra tool we touch (Docker, k8s, Tailscale, Cloudflared, Caddy, Hugo) is Go. Same language for Mercury and its operating environment.

---

## 12. Where this wiki ends and the rest of the docs begin

- For the **module-by-module port plan** (which Mercury components need rewriting, in what order, with what Go libraries), see `MERCURY_GO_REWRITE_ASSESSMENT.md`.
- For the **deeper Rust vs Go vs Python analysis**, see `LANGUAGE_COMPARISON.md`.
- For the **12-week summer-course curriculum** that uses Mercury as the project, see `SUMMER_COURSE_PLAN.md`.
- For **practice material**, the `knowledgebase/go-learn/` directory has 42 saved pages from the Tour, Go by Example, and the Go blog.
- The **official Go docs** at https://go.dev/doc/ are the source of truth; this wiki is a curated path through them.
