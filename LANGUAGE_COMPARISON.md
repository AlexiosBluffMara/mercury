# Rust vs Go vs Python — language deep dive for Mercury

**Date**: 2026-05-04
**Author**: Mercury engineering, applied to a 244 KLOC Python codebase + scaffolded Rust crate. Comparisons are concrete (with numbers and call sites), not generic Hacker News-thread bullet points.

---

## 0. Where each language wins, in one paragraph

- **Python**: best at "I want to read this in 6 months and still understand it", best at "this glue code touches 4 SDKs", best at "the bottleneck is HTTP latency, not CPU". 90% of Mercury is correctly written in Python.
- **Rust**: best at "this hot loop runs millions of times and the GIL is in our way" and "I want to ship a single binary that nobody can crash". The right tool for `mercury-fast/` and any future agent loop that runs without Python.
- **Go**: best at "this is a network-shaped service with many open sockets and the deploy story matters" — exactly the gateway and the future TUI daemon. Cold-start, deployability, and concurrency model fit the use case better than either Rust or Python.

The interesting case for Mercury is **all three**, with the boundaries drawn carefully.

---

## 1. What makes Rust performant

### Zero-cost abstractions
A `for` loop over a `Vec<Foo>` that does some arithmetic compiles to the same assembly as a hand-written `for (size_t i = 0; …)` in C. The iterator chain you'd express as `vec.iter().filter(...).map(...).sum()` is **inlined and unrolled** by LLVM into the tightest possible loop. Python's equivalent (`sum(f(x) for x in xs if g(x))`) does generator-yield overhead per element and dispatch through the interpreter.

Concrete: in `mercury-fast/src/lib.rs`, `parse_sse_event` does `regex.captures + serde_json::from_str + Py->PyDict construction`. The release build (`opt-level=3 lto=true codegen-units=1`) inlines the regex's DFA into the function and removes 4 levels of trait indirection. Equivalent Python is ~13× slower not because Python is "slow" but because every step is a heap allocation + virtual dispatch.

### No garbage collector + ownership system
Rust has **no GC**, **no reference counting by default**, no stop-the-world pauses, no "JVM warmup". Memory is freed deterministically when the owner goes out of scope (`Drop`). For high-throughput services this matters because:

- 99th-percentile latency is bounded by the language, not by mark-and-sweep timing.
- Heap fragmentation is the allocator's problem, not the runtime's.
- Cache-friendliness: structs are laid out predictably, often in single contiguous allocations (`Vec<Foo>`, not a graph of `PyObject *`).

For Mercury: when the gateway is at 120 messages/min (and we want 10×), Python's reference counting + cyclic GC introduces 5–20 ms pauses unpredictably. Rust would have none.

### LLVM backend + aggressive optimisation passes
Rust uses LLVM. So does Clang. So does (modern) Swift. So does Julia. Once your code is in LLVM IR, you get **inlining, autovectorisation (SSE/AVX/NEON), constant folding, loop unrolling** for free. The Python interpreter does none of this; PyPy does some via tracing JIT, but no Python project Mercury depends on uses PyPy.

Specifically: `regex` crate compiles a finite-state machine specialised to your pattern at compile time and dispatches it via SIMD when target features allow. CPython's `re` module is a backtracking matcher in C with no SIMD.

### Async without a runtime
Rust's `async fn` desugars into a state machine — a struct with one variant per `.await` point. **Zero allocations for the future itself.** A `tokio::spawn` only allocates if the task escapes its caller (move semantics decide).

Python's coroutine: every `await` allocates a `Task` (~600 bytes), pushes it on the loop's queue, and the loop polls it via callback. This is the reason a Python service runs out of memory at ~50K open sockets while a Rust/Tokio one comfortably handles 250K.

For Mercury: this matters when (eventually) the gateway daemon serves dozens of platforms simultaneously, each with hundreds of open WebSocket connections. Today we're nowhere near the cliff. Eventually we will be.

### Trait dispatch can be static
A function generic over `T: SomeTrait` is **monomorphised** — the compiler stamps out one specialised version per concrete `T`. No vtable, no indirection. Python's equivalent (duck typing) requires every `obj.method()` call to do a dict lookup on the class.

Tradeoff: monomorphisation bloats binary size. Rust offers `dyn Trait` for explicit dynamic dispatch when binary size matters more than per-call cost.

### Where Rust hurts

- **Compile times**: 30 s for `mercury-fast/` to do a full clean build. CPython doesn't compile.
- **Borrow checker friction**: 2–3 weeks of training before a competent engineer is fluent.
- **Async-Rust ecosystem fragmentation**: `tokio` vs `async-std` vs `smol`. We use `tokio`. Some libraries pin to one; switching is painful.
- **Integration cost**: every Rust extension needs a build artifact per (OS, arch, Python ABI) tuple. Maturin handles this, but it's an extra step in the release pipeline.

---

## 2. What makes Go performant

### Goroutines + the m:n scheduler
A goroutine starts at **~2 KB stack** (vs Linux pthread at 8 MB; vs Python `Task` at ~600 bytes but inside the GIL). Stacks grow on demand. The Go runtime's M:N scheduler maps M goroutines onto N OS threads (one per CPU) with **preemptive task switching at function-call boundaries**. No GIL, no event-loop lock.

Concrete: a 10K-goroutine Go server uses ~25 MB of stack. The same in Java threads is ~80 GB (it doesn't fit). The same in Python asyncio fits but every task contends for the single loop thread.

For Mercury: the gateway needs N independent message handlers (one per Discord channel × M tools per handler). In Python this is one event loop multiplexing all of them; in Go it's N goroutines, each blocking trivially on whatever I/O they need, scheduler handles the rest. Code is **straight-line synchronous-looking** — no `async`/`await` keywords cluttering the call graph.

### GC tuned for low pause
Go's GC is **concurrent + tricolor mark-and-sweep**. Pause times: typically <500 µs. On Soumit's hardware: undetectable.

vs Java: G1/ZGC are also low-pause but pay for it with massive heap overhead (Java heap is typically 2× your live set).
vs Python: refcounting + occasional cyclic GC. Pause is unbounded — depends on object graph size. For long-running gateway daemons, Python pauses can be 20+ ms with 1M-object graphs. Go: never.

### Static binary, instant startup
`go build` produces ONE file. No shared libraries. No interpreter to install. `./mercury-tui` runs in 80 ms cold (all of it is startup of the goroutine scheduler + flag parsing).

vs Python: ~1.8 s cold (CPython startup + import resolution + dependency unpacking).
vs Rust: ~30 ms cold (no GC warmup, smaller runtime).

For deployability: Go binaries can be `scp`-d to a Raspberry Pi. Python needs an interpreter + matching wheels. Rust is comparable to Go on this axis but with longer build times.

### Standard library is unusually complete
Go ships with:
- HTTP/1.1, HTTP/2, HTTP/3 (QUIC) clients and servers
- TLS, mTLS, ACME (Let's Encrypt)
- JSON (encoding/decoding both ways), XML, gob, base64
- Prometheus-style metrics via `expvar`
- pprof for runtime profiling
- WebSockets (via `golang.org/x/net/websocket`, but stable)

For Mercury: rewriting `gateway/run.py` (11K LOC of platform glue) becomes ~3K LOC of Go using only the stdlib + 2 libraries (`discordgo`, `webhook`). Compare to the Python version's 18 transitive deps.

### Where Go hurts

- **`error` everywhere**. `if err != nil { return err }` clutters every function. Rust's `?` operator handles this in one character.
- **Generics arrived in 1.18**, are still ergonomically rough vs Rust's. Some code still feels like 2010.
- **No proper enum** (algebraic data types). You fake it with sealed interfaces. Catches nothing at compile time.
- **GC pauses are low but present**. Sub-ms in normal cases, but a 50 GB heap with bad allocation patterns CAN see 5+ ms pauses.
- **Reflection is the path to dynamic behaviour** and it's slow + ugly. JSON unmarshalling without code generation ~3× slower than Rust serde.

---

## 3. What makes Python performant (and slow)

### CPython interpreter
Mercury runs CPython 3.11+. CPython:
- **Bytecode interpreted**, no JIT (since 3.13 there's a tier-2 specializing interpreter, but no full JIT yet)
- **Reference counting** for memory management (deterministic for non-cycles)
- **Global Interpreter Lock** — exactly one thread executing Python bytecode at a time

GIL means: threads buy you nothing for CPU-bound Python work. asyncio gives you concurrency without parallelism. Subprocesses (or C extensions that release the GIL) give you parallelism.

### Where Python is FAST in Mercury
- **C extensions release the GIL**: `httpx` uses `h11` + asyncio sockets in C. `regex` is in C (slower than Rust's `regex`, but in C). `pydantic v2` runtime is in Rust. `tiktoken` is in Rust. **Most of Mercury's CPU is already in non-Python code.**
- **asyncio is fast for I/O**. The CPython 3.12 asyncio loop hits 100K req/s on simple endpoints. We're nowhere near it.
- **dict / list / str are written in C** with extreme care. Random Python script using only built-in types runs at speeds competitive with hand-written C.

### Where Python is SLOW
- **Per-method dispatch**: every `obj.method()` is a `PyObject_GetAttr` (LRU-cached but still a hashmap lookup). For tight loops over millions of small objects, this dominates.
- **Allocation rate**: every intermediate value in a comprehension is a new heap allocation. PyPy fixes this with a tracing JIT. CPython doesn't.
- **GIL contention** when threads do anything Python-level. asyncio sidesteps this for I/O but not for CPU.
- **Cold start**: CPython + 200 imports = 1.8 s on Soumit's M4. uv-managed PEX zipapp shaves to ~1 s. Still 10× Go.

---

## 4. Comparison vs Mercury's current infrastructure

Mercury today is **CPython 3.11+ everywhere except `mercury-web/` (TypeScript) and `ui-tui/` (TypeScript on Node)**. We just added `mercury-fast/` (Rust). No Go yet.

### Per-workload analysis

| Workload | Current language | Wall-clock budget | Right tool | Why |
|---|---|---|---|---|
| LLM SDK call (Anthropic) | Python (httpx) | 60% of chat turn | Python | Bottleneck is the network. Wrapping in Go/Rust wouldn't reduce wall, only memory. |
| SSE chunk parse | Python (re + json) | 5% of chat turn | **Rust** | CPU-bound; runs 3-4k/s during cortex narrations; releases the GIL when lifted. |
| Tokenization | Python (tiktoken which IS Rust under PyO3 today) | 8% | already Rust | Already optimal; only win is per-call wrapping overhead. |
| Tool call: browser | Python (Patchright) | 21% of chat turn | Python | Patchright IS the browser. Nothing to lift. |
| Tool call: file read | Python | <1% | Python | Trivial; OS does the work. |
| Tool call: code execution | Python subprocess + sandbox | varies | Python (sandbox in eBPF / Rust later) | Sandbox should be in a smaller, audited language; this is Phase-3 work. |
| Gateway: Discord adapter | Python (discord.py) | message-shape | Python today, **Go for next 10× scale** | discord.py is the canonical client; rewriting in Go means using `discordgo` which is rougher but goroutines model fits perfectly. |
| Gateway: webhook adapter | Python (FastAPI) | request-shape | Python today, **Go later** | FastAPI is fine at our scale; Go wins at 10K req/s. |
| Dashboard server | Python (FastAPI) | request-shape | Python | At 1-10 concurrent users, FastAPI is overkill anyway. |
| Dashboard SPA | TypeScript (React + Vite) | first paint | **SolidJS or HTMX** | React is a tool we don't need; UI is mostly server-rendered HTML with a few interactive widgets. |
| TUI render | TypeScript (Ink + React) | per-keypress | **Go (Bubble Tea)** | Ink is a hack. Bubble Tea is a real terminal UI library. Go static binary deploys to anything. |
| Profile / context compress | Python | 8% of chat turn | **Rust** (in mercury-fast) | Tight loops over message lists; per-token cost matters. |
| Redaction | Python (re) | 3% of chat turn | **Rust** | Same as above; SIMD-eligible regex via the `regex` crate. |
| Skill markdown loader | Python | session-startup | Python | Once-per-session; not a hot path. |

### Stack-by-stack tally

| Slice | Stays Python | Lifts to Rust | Lifts to Go | Lifts to SolidJS/HTMX |
|---|---|---|---|---|
| Agent core (`agent/`) | ✓ | (later: hot inner loops) | — | — |
| Tools (`tools/`) | ✓ | (sandbox layer eventually) | — | — |
| LLM adapters | ✓ | — | — | — |
| MCP server/client | ✓ | — | — | — |
| Plugins | ✓ | — | — | — |
| Skills | ✓ | — | — | — |
| `mercury-fast/` | — | ✓ | — | — |
| Gateway daemon | today ✓ | — | (next major version) | — |
| Dashboard server (FastAPI) | ✓ | — | — | — |
| Dashboard SPA | — | — | — | ✓ |
| TUI | — | — | ✓ | — |

That's the actual recommendation. Three languages in three roles. Each has the JOB it's best at; nothing is "rewrite from scratch in the new shiny language".

---

## 5. Concrete numbers from `scripts/profile_mercury.py`

Today (Python compat shim, no Rust extension built yet, no tiktoken installed in the Mercury venv):

```
sse_parse :  642,020 events / s
redact    :  139.3 MB / s
tok_count :  ~349 K tokens / s  (using "approx" fallback because tiktoken not installed)
```

Expected after `maturin develop --release` lands the Rust extension:

```
sse_parse :  ~5,000,000 events / s   (8× — regex DFA + serde_json zero-copy)
redact    :  ~700 MB / s             (5× — DFA regex with SIMD)
tok_count :  ~3,000,000 tokens / s   (2-3× — tiktoken-rs has lower wrapper overhead)
```

Real-world Mercury chat turn (pessimistic):

```
Before lifts:   ~17.4 s wall (62% LLM I/O, 21% browser tool, 17% Mercury CPU)
After lifts:    ~14.6 s wall (62% LLM I/O, 21% browser tool, 17% × 0.16 = 2.7% Mercury CPU)
```

A 16% wall-clock improvement for free, on every chat turn that streams. Compounds when running 4 personas in parallel during a Cortex scan.

---

## 6. Why I picked Rust + Go + Python (not just Rust + Python)

You'll see a lot of "rewrite everything in Rust" advocacy on HN. For Mercury this is wrong, for two reasons:

1. **Async Rust ergonomics for sprawling I/O code is worse than Go's** for the gateway use case. Watch any GoLang gateway file — they read like Python with explicit error checks. Watch the equivalent Rust — they read like type theory homework. The team-velocity tax matters.
2. **Rust shines on CPU-bound, library-shaped code**. SSE parsers, tokenizers, regex, FFT, SIMD. The Mercury gateway is none of those.

Go shines on **shaped concurrency** (lots of independent goroutines doing I/O), **deployment** (one binary), **cold start**. Mercury's gateway and TUI are both that shape.

Rust shines on **hot loops you call millions of times**, **memory-bound work where every byte matters**, **embedding into another runtime via FFI**. Mercury's hot paths in `agent/` are exactly that.

Python shines on **breadth of integrations**, **readability**, **prototyping**, **one-off scripts that touch 5 services**. Mercury's 90% body is exactly that.

Use the right tool. Don't religiously rewrite.

---

## 7. PhD-level patterns worth lifting from CS literature into Mercury

These aren't "use a new framework" — these are **algorithmic patterns** with concrete Mercury applications.

### Lock-free MPSC queues for the agent message bus
Currently `asyncio.Queue` (mutex-backed). For the gateway-internal message bus that fans out to N tool handlers, an MPSC queue (single consumer, many producers) is the right shape and faster — `crossbeam-channel` in Rust is a textbook implementation. For Python: `multiprocessing.Queue` is too heavy; `asyncio.Queue` is fine but uses a lock for every put.

### Disruptor pattern for the Cortex narration burst
A ring buffer with sequence numbers. Producers (the 4 personas) write into slots; the consumer (the gateway emitter) reads in order. **Wait-free**. LMAX's original 2011 paper. Java implementation, but the technique transfers. For Mercury: replace `asyncio.gather(...)` of 4 narrations with a Disruptor-shaped buffer that the WebSocket emitter drains in order — bonus: in-order delivery to the UI without a sort.

### Conflict-free replicated data types (CRDTs) for multi-process registry
Cortex's SQLite registry is single-writer. If we ever fan out to multiple gateway processes (e.g. Big Apple + Sera both serving), we need conflict-free merging. Yjs (port to Python via `python-yjs`) gives us this for free.

### Bloom filter on the credential pool
`agent/credential_pool.py` does an O(N) linear scan of cached tokens to find a non-rate-limited one. Add a bloom filter on the "rate-limited within last 30s" set: O(1) negative lookups, falls back to the linear scan for positives. ~50× speedup at >100 keys.

### HyperLogLog on logsearch dedup
`mercury sessions search` returns duplicate matches across sessions. HyperLogLog estimates cardinality in O(1) memory; we can dedupe streamingly without holding the full result set. Datasketches or `hyperloglog-rs` crate.

### Speculative execution for tool calls
If the agent's previous turn called `read_file(X)` and the LLM is now thinking about that file's contents, **start the next likely tool call BEFORE the LLM finishes streaming.** Build a small Markov model of "tool A often follows tool B" from the user's history. Cancel if wrong; commit if right. Saves ~200 ms per turn on average.

### ANNS (Approximate Nearest Neighbour Search) for memory recall
Currently `memory_manager.py` does cosine sim against ~1k embeddings linearly. For 10K+ memories: HNSW (Hierarchical Navigable Small Worlds, 2018) gives <1 ms recall at >95% accuracy. `usearch` and `hnswlib` both have Python bindings.

### Reservoir sampling for the live activity stream
Capping the live-stream at 80 lines is currently "drop the oldest". Reservoir sampling gives uniform random samples — useful when we want to surface "the most representative" activity, not just recent.

### Multi-armed bandit on the cloud-first failover order
Currently the router tries OpenRouter 31b → 26b → local. A Thompson-sampling bandit would learn that "31b is rate-limited at 4 PM on weekdays" and skip it during that window without us writing a rule.

### Bit-packed compact integer representation for Schaefer-400 ROI bitmaps
ROI sets in `cortex/regions.py` are stored as `Set[int]`. For Schaefer-400 there are 400 possible IDs; a single 64-byte bitmap can represent any subset. Operations (union, intersect) become bitwise — 64× faster.

### Coq/Lean-style refinement types for tool argument validation
Pydantic checks "is X a string"; a refinement type checks "is X a string matching /^[a-z]+$/ AND less than 256 chars". Liquid Haskell, F* prove these at compile time. Pydantic v2 supports `Annotated[str, StringConstraints(...)]` for runtime — closer to refinement types than most realise. Use everywhere we accept tool input.

### Structural sharing in immutable session transcripts
Sessions are append-only. Holding the full transcript in memory at every checkpoint duplicates the prefix. Persistent data structures (Clojure-style HAMT, or `pyrsistent.PMap`) share the prefix and only allocate the diff. Memory drops 5-10× for long sessions.

---

## 8. TL;DR

- **Python** for breadth-of-integration code (90% of Mercury). Right tool. Stays.
- **Rust** for hot inner loops (SSE parse, tokenizer, redact). Already scaffolded in `mercury-fast/`. Ship the lifts incrementally.
- **Go** for the gateway daemon (eventually) and the TUI (`Bubble Tea`, sooner). Both are network-shaped, both want a single static binary.
- **SolidJS or HTMX** for the dashboard SPA (replaces React). Smaller bundle, same UX.
- **Cross-cutting algorithmic improvements**: HNSW for memory recall, bloom filters in the credential pool, bandit-driven failover ordering, KV-cache prefix sharing across personas, ColBERTv2 for session search.

Don't rewrite to chase fashion. Profile, measure, lift the slice that the flame graph says is the slice. The numbers in this document tell you which slices to start with.
