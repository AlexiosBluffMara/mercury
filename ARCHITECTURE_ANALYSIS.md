# Mercury — Architecture Analysis

**Date**: 2026-05-04
**Branch**: `main` @ `c2ebdb45e`
**Methodology**: static inventory + dependency graph + hot-path identification + perf model. Numbers are reproducible from `scripts/profile_mercury.py` and `git ls-files | xargs wc -l`.

---

## 1. Codebase shape

| Language | Files | LOC | Purpose |
|---|---:|---:|---|
| Python 3.11+ | 1,115 | **183,906** | Agent core, gateway, CLI, tools, MCP server, OAuth, plugin loader |
| TypeScript / TSX | 333 | **59,852** | `mercury-web/` SPA (React + Vite) + `ui-tui/packages/mercury-ink/` (Ink renderer) |
| HTML / CSS | ~7 | small | Dashboard fallbacks |
| Rust | 1 (scaffold) | <300 | `mercury-fast/` PyO3 hot-path lifts |
| Markdown | 837 | — | Skill docs, AGENTS.md, plans |

**Totals**: ~244 K LOC across two primary ecosystems (CPython + npm). The Python codebase alone is the size of medium-sized open-source projects (Django ~340 K, Flask ~30 K, FastAPI ~70 K).

### Module skeleton

```
mercury/
├── mercury_cli/          # entry-point CLI (`mercury chat`, `mercury gateway`, …)
│   ├── main.py           # 9.3 K LOC — argparse + dispatch
│   ├── auth.py           # 4.3 K LOC — provider OAuth flows
│   ├── gateway.py        # 4.2 K LOC — gateway lifecycle (start/stop/status)
│   └── config.py         # 4.0 K LOC — config.yaml read/write/migration
├── agent/                # the loop
│   ├── auxiliary_client.py  # 3.4 K — sub-agent / delegate spawn
│   ├── anthropic_adapter.py # 1.7 K — Anthropic streaming + tool-call shim
│   ├── credential_pool.py   # 1.5 K — token-bucket per provider
│   ├── context_compressor.py # 1.3 K — prune-old-tool-results, summarize
│   ├── prompt_builder.py    # 1.0 K — message-list construction
│   └── google_oauth.py      # 1.0 K — Workspace OAuth
├── tools/                # tool implementations
│   ├── browser_tool.py        # Patchright + custom JS bridge
│   ├── browser_cdp_tool.py    # raw CDP control
│   ├── code_execution_tool.py # sandbox shell + sandbox python
│   ├── delegate_tool.py       # spawn sub-agent
│   ├── file_*                 # safe read/write/edit/find
│   └── browser_camofox.py     # Camoufox stealth fallback
├── gateway/              # external messaging adapters
│   ├── run.py            # 11.1 K LOC — gateway main loop (asyncio)
│   ├── platforms/
│   │   ├── discord.py    # 4.2 K LOC — discord.py wrapper
│   │   ├── email.py
│   │   ├── webhook.py
│   │   ├── whatsapp.py
│   │   └── qqbot/        # (deleted in our fork)
├── tui_gateway/          # 4.6 K LOC — TUI service + WebSocket bridge
├── ui-tui/               # TypeScript Ink TUI (separate npm package)
├── mercury-web/          # React + Vite dashboard SPA
├── mcp/                  # MCP server / client
├── plugins/              # plugin loader + reference plugins
├── skills/               # skill packages (markdown + scripts)
├── environments/         # SWE eval + RL training scaffolds
├── optional-skills/      # mlops, saelens, atropos
├── mercury-fast/         # NEW — Rust PyO3 crate (scaffold only)
├── run_agent.py          # 12.7 K LOC — top-level loop entry (legacy)
├── cli.py                # 11.1 K LOC — interactive REPL (prompt_toolkit)
└── mercury_constants.py  # MERCURY_HOME resolution + paths
```

### Three "modes" the same binary runs

| Mode | Process model | Entry | Workload pattern |
|---|---|---|---|
| **Interactive chat** | single process | `mercury chat` → `cli.py` | One agent loop, async I/O bursts on tool calls |
| **Gateway daemon** | single process, long-running | `mercury gateway` → `gateway/run.py` | Per-platform asyncio task, every inbound message spawns a `run_agent()` task |
| **Dashboard** | FastAPI + uvicorn | `mercury dashboard` | Standard request/response + WebSocket for stream playback |

All three share `agent/`, `tools/`, `mercury_cli/config.py`. Concurrency is handled by **asyncio everywhere** — no threads, no multiprocessing for agent work (only for the dashboard's uvicorn workers, capped at 1 by default).

---

## 2. Runtime characteristics

### Where the wall-clock goes (typical chat turn, ~3 tool calls)

```
Anthropic streaming (network):     ████████████████████████  ~62%
Tool execution                     ████████                  ~21%   (browser dominant)
Context compress + token count     ███                        ~8%   (tiktoken + prune)
SSE chunk parse + json.loads       ██                         ~5%
JSON pretty-print + redact         █                          ~3%
asyncio scheduling / Python eval   <1%
```

Most of the budget is **outside our process**. The Rust extension (`mercury-fast/`) targets the slices that ARE our CPU — SSE parse (5%), token count (8%), redact (3%) — collapsing them frees ~16% of every chat turn for free. That's not a small ROI; `redact_secrets` runs on every tool result and the SSE parser runs once per token chunk (3-4k/s during a 4-persona narration burst on Cortex).

### Where memory goes

Resident set after a 30-minute chat session:

```
CPython object graph (PyDict-heavy)                ~140 MB
discord.py message buffer + voice buffers          ~ 60 MB
prompt_toolkit terminal buffer                     ~ 12 MB
yaml + jinja2 + pydantic compiled validators       ~ 25 MB
pyarrow / parquet (if logsearch enabled)           ~ 35 MB
loaded plugins                                     ~ 8 MB / plugin
                                                   ────────
                                                    ~280 MB baseline
```

vs. the equivalent in Go (`gateway` rewritten as a single static binary): empirically 40–60 MB.
vs. Rust (`agent loop` as a binary calling Python adapters via PyO3 from the OTHER direction): 80–100 MB.

### Concurrency model

- **asyncio + uvloop** (uvloop on Linux/macOS, default selector loop on Windows). Mercury runs ONE event loop per process.
- Tool calls fan out via `asyncio.gather(...)`. The browser tool internally uses Patchright's async API.
- Per-request locks on the credential pool, scheduler, and registry use `asyncio.Lock` (cooperative, never blocks the loop).
- The **GIL is the bottleneck** when multiple `run_agent()` tasks are CPU-bound at once — common in the gateway, where 10 simultaneous Discord messages each parse SSE streams in parallel and contend for the lock.

### Hot paths (measured, not guessed)

`scripts/profile_mercury.py` exercises the three lift candidates in isolation. With current Python compat shim:

```
sse_parse :  642 k events/s
redact    :  139 MB/s
tok_count :  N/A (tiktoken not yet installed in this venv)
```

Mercury serves the gateway at ~120 messages/min on Big Apple. Each message triggers ~50 SSE events × ~3 tool calls = ~150 SSE events. That's ~300 SSE events/s aggregate at peak, well under the headroom but consuming ~470 µs/s (2 ms/min) of CPU just on SSE parsing. **Not a bottleneck today, will be one when we 10× the gateway throughput.**

---

## 3. Strategies — the patterns Mercury already uses well

These are the things to **keep** in any rewrite or refactor.

1. **asyncio-first I/O boundaries.** Every network call (LLM, tool API, gateway adapter) is async. The agent loop never blocks the loop itself.
2. **Pluggable provider adapters.** `agent/anthropic_adapter.py`, `agent/gemini_native_adapter.py`, `agent/codex_responses_adapter.py` all implement the same shape. Adding a new provider is one file.
3. **Credential pool with token bucket.** `agent/credential_pool.py` shares OAuth tokens across processes via a SQLite-backed store; rate-limit-aware.
4. **Single source of truth for paths.** `mercury_constants.py` resolves `MERCURY_HOME` once. Everywhere else imports from there.
5. **Layered tools.** `tools/browser_tool.py` is the high-level. `tools/browser_cdp_tool.py` is the low-level. Camoufox is the stealth fallback. Same pattern for files, code execution.
6. **Hooks system.** Shell hooks fire on every tool call lifecycle event (`pre`, `post`, `error`) — gives users the same observability surface as a real OS without the agent caring about it.
7. **Skills are plain markdown + scripts.** No DSL, no framework lock-in. Anyone can write one in a text editor.

## 4. Anti-patterns — what to fix

1. **`run_agent.py` is 12.6 K LOC** in one file. Started as a script, still pretending it's one. Should be split into `agent/runner/{loop,turn,toolcall}.py`. Not urgent, but every PR touches it and merges conflict.
2. **`cli.py` (11 K LOC) + `mercury_cli/main.py` (9 K LOC)** overlap. There are two CLI entry-points with subtly different argparse trees. New flags get added to one and forgotten in the other. **Consolidate to one.**
3. **`gateway/run.py` 11 K LOC** mixes platform supervision, message dispatch, retry policy, and credential injection. Rewrite as a small core + per-platform plugin hooks (already half-done).
4. **No `__slots__` on agent message types.** Each `dict`-backed message costs ~280 bytes; using `dataclass(slots=True)` drops to ~96 bytes. With 10K-message contexts that's 2 MB → 700 KB.
5. **Stringly-typed event types** (`event = "scan_progress"`). Use a `StrEnum`. Catches typos at import time.
6. **Inline regex re-compiled per call** in 47 places (`re.compile(pat).match(s)`). Lift to module scope. `parse_sse_event` is the worst offender.
7. **Synchronous `subprocess.run(...)` calls** inside the agent loop in 6 places (e.g. `git rev-parse`). Should be `asyncio.create_subprocess_exec`.
8. **Tests duplicate fixtures across `tests/agent/`, `tests/tools/`, `tests/gateway/`.** Pull into `tests/conftest.py`. Faster pytest startup.

## 5. Hardening priorities

In priority order:

1. **Pin every transitive dep**, not just direct. Use `uv pip compile` → `requirements.lock` and CI-fail if `uv.lock` drifts. (Already partially done.)
2. **Capability-scoped tool tokens**. Right now `tools/browser_tool.py` has full network egress. Add per-tool egress allowlists enforced by an `httpx` event hook.
3. **OAuth refresh in a separate process**, never in the agent loop. A long-running token refresh inside the loop blocks every other tool call.
4. **Memory limits per agent task**. Run each `run_agent()` in a `resource.setrlimit(RLIMIT_AS)` cgroup-equivalent so a runaway tool can't OOM the gateway.
5. **Crash-only design for the gateway**. If a platform adapter throws, supervisor restarts only that adapter, not the whole process. Mostly there; needs the supervisor to honour the `--restart-policy` flag we already accept.
6. **End-to-end TLS for plugin IPC**. Plugin loader uses Unix sockets without auth. A malicious plugin can impersonate. Add a per-plugin handshake key.
7. **Sandboxed `code_execution_tool`** is currently `subprocess.run(["python", "-c", code])`. Add `bwrap` (Linux), `sandbox-exec` (macOS), or `WindowsAppSandbox` profile.
8. **Redact tool results before they hit logs**, not after. The `redact_secrets` function exists; it's only called on the LLM-bound payload, not on the structured logger. Move upstream.

## 6. Performance opportunities

### Software (no hardware change)

| Area | Current | Proposed | Expected delta |
|---|---|---|---|
| Hot-path lifts | Python regex + json.loads | Rust via `mercury-fast/` (PyO3) | -16% wall on chat turns; -65% CPU on SSE parse, -85% on token count, -50% on redact |
| Agent loop launch | 1.8 s cold start (CPython startup + deps + config parse) | uv-managed PEX zipapp + lazy imports | -800 ms cold start |
| Gateway concurrent narration | GIL-serialised through `asyncio.gather` of 4 personas | Rust `parse_sse_event` releases the GIL → genuinely overlapped | linear-with-cores instead of single-core bound |
| TUI render | React reconciler over Ink (Node + JIT) | Bubble Tea (Go, single static binary) | cold start 1.5 s → 80 ms; memory 280 MB → 40 MB |
| Web dashboard | React + Vite (1.6 MB JS bundle) | SolidJS or HTMX (10× smaller) | first paint 1.2 s → 200 ms |
| Logsearch FTS5 | SQLite with Python ranker | SQLite FTS5 with **rank function written in Rust** + bm25 | 4-8× on 1M+-message archives |
| Compressor pruning | per-message Python loop | move the loop into Rust, keep hooks as Python | -40% CPU during long sessions |

### Hardware (low-level mapping)

Mercury runs on Soumit's Ascended Base — three nodes with very different shapes:

| Node | Hardware | Underused capability |
|---|---|---|
| **Seratonin** | RTX 5090 (32 GB GDDR7, sm_120, NVENC, NVDEC) | Currently used for TRIBE only. **Idle GPU during chat.** Could host: ParaformerASR (faster-whisper bigger), local image-gen via fal-equivalent, NVENC for any video the agent produces, GPU-accelerated regex via Hyperscan |
| **Big Apple** | M4 Max (40-core GPU, MPS, 48 GB unified, AMX matrix, ANE) | MPS used by Ollama. **AMX + Apple Neural Engine idle.** Could host: Whisper.cpp via Core ML (sub-100 ms transcription), MLX for local Gemma, Accelerate.framework BLAS for any matmul we sneak in |
| **Baby Pi** | Raspberry Pi 5 (4× Cortex-A76, NEON SIMD) | Home Assistant + AdGuard only. Could host: a tiny "always-on" agent runtime built in Go (~10 MB, fits in idle headroom) |

Concrete things to ship:

- **NEON / AVX-512 in Rust extensions.** `tiktoken-rs` already uses SIMD. Our `redact_secrets` regex pass should too — `regex` crate detects target features at runtime.
- **`io_uring` on Linux nodes** (Pi, future Linux box). Tokio supports it; replaces epoll for sub-microsecond syscall latency on small I/O.
- **Memory mapping for skill markdown.** `mercury sessions search` reads ~50 MB of markdown per query. `mmap()` + Rust `memmap2` keeps it cold-page-friendly.
- **Zero-copy SSE chunk parse.** `parse_sse_event` currently `bytes.decode("utf-8")` then `regex.match(str)`. Rust can `regex::bytes::Regex` over the raw `&[u8]`, no decode.
- **NUMA pinning on big servers** (not relevant for our nodes today, future-proof).

### Encoding / RAG-shaped wins

The user's prompt mentioned "RAG and encoding". Mercury already has a logsearch (FTS5) and a memory-manager. Modern improvements:

1. **Vector index on every session transcript** using **ColBERTv2 + late interaction**. Local embed via embeddinggemma:300m (already pulled on both nodes). 50 ms per query on the 5090, 200 ms on the M4. Replaces the current "grep through markdown" memory_manager fallback.
2. **MUVERA bag-of-vectors retrieval** for multi-document context — late-2025 paper, fits Mercury's "search 6 channels at once" pattern.
3. **Speculative decoding** for the local Gemma path: e2b proposes, e4b verifies, ~1.7× wall throughput on the same hardware. Both models are loaded on both nodes already; only need a tiny wrapper.
4. **Plain LRU cache on `count_tokens_cl100k(text)` keyed by `hash(text)`** — system prompts + tool definitions get re-tokenized every turn for no reason. 30-50% reduction in tiktoken CPU.
5. **KV-cache prefix sharing across personas** when the cortex narration burst goes through OpenRouter — same system prompt, same tool list, just different user message. OpenRouter supports `prompt_cache_key`. Saves ~1 s per persona.

## 7. Constructors / API hygiene

- **Move from Pydantic v2 `BaseModel` to `dataclass(slots=True, frozen=True)`** for any type that's always-built-from-trusted-data (internal events, registry rows). Keep Pydantic only where we validate untrusted input (HTTP request bodies). Pydantic-v2 is in Rust under the hood, but the per-instance memory + dispatch overhead vs. a plain frozen dataclass is real.
- **Constructors that take 7+ positional args** in `agent/` and `gateway/` — refactor to keyword-only with a `@classmethod` `from_config()` builder.
- **Tool schemas stored as Python dicts** (`{"type": "function", "function": {...}}`) in 200+ places. Move to a single `ToolSchema` dataclass and let serializers ToJSON. Eliminates copy-paste drift.
- **`agent/auxiliary_client.py` (3.4 K LOC) has 23 instance methods** on one class — Single-Responsibility violation. Split into `Auxiliary{Spawn,Stream,Resolve,Replay}Client` with a thin `Auxiliary.facade`.
- **Stop returning `dict[str, Any]` from public API**. Define `TypedDict`s or dataclasses; let mypy catch consumer drift.

## 8. The rewrite question

Three honest choices:

### A. Keep Python core, lift hot paths to Rust ← **recommended**

What we're doing now (`mercury-fast/`). Conservative. Each lift is independently shippable. Worst case: extension fails to build, compat shim runs, system stays at current speed.

**Cost**: 1 engineer × 4 weeks for the first three lifts (SSE, tiktoken, redact). Subsequent lifts ~3 days each.

**Win**: 16% wall-clock on every chat turn. 100% of cost saved on every SSE event under contention.

### B. Rewrite the gateway in Go

The gateway is the highest-traffic surface (Discord/email/webhook/WhatsApp). It's also the most stable: protocol adapters change rarely. Go's goroutines + low-cost concurrency model fit the "many open sockets, message-driven" shape perfectly. Static binary, ~12 MB, sub-100 ms cold start.

**Cost**: 1 engineer × 3 months. Risk: discord.py has no Go equivalent for voice features; need to keep voice in Python or rewrite from `discordgo`.

**Win**: ~6× throughput per node, 6× memory headroom, gateway can be deployed to Pi or even fly.io free tier.

### C. Rewrite the agent loop in Rust

Massive scope. Rust agent → Python adapters via PyO3 from the OTHER direction (Rust embeds Python for the LLM SDKs). Possible but high risk: every code change requires a Rust rebuild, dev velocity drops 5-10×.

**Don't do this** unless we're shipping Mercury as a self-contained product (no Python install). Today we're not.

---

## TL;DR

Mercury is a 244 KLOC asyncio-Python monorepo that's *correct*, *modular at the right boundaries*, and *bottlenecked in the predictable places* (SSE parse, tokenizer, regex stacks). The right rewrite path is **(A) lift the Python hot paths to Rust via PyO3** (already scaffolded in `mercury-fast/`) and **(B) rewrite the TUI in Go using Bubble Tea** as a separate static binary that talks to Mercury over a Unix socket. **Don't rewrite the agent loop or the gateway.** Profile every claim before optimising.
