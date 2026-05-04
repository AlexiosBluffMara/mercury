# mercury-fast

Performance-critical Mercury hot paths in Rust, exposed to Python via PyO3.

## What's in here

| Symbol | Replaces | Why |
|---|---|---|
| `parse_sse_event(line)` | a regex + `json.loads` chain in `agent/streaming.py` | runs ~3-4k calls/s during a 4-persona narration burst; Rust regex + serde-json drops per-call overhead from ~80 µs → ~5-12 µs and releases the GIL during the parse |
| `count_tokens_cl100k(text)` | Python `tiktoken.get_encoding("cl100k_base").encode(...)` | tiktoken-rs avoids the Python wrapping overhead and warms instantly via `OnceLock` |
| `redact_secrets(text)` | the regex stack in `agent/redact.py` | bulk pass over tool-call argument blobs; dropped CPU during compressor passes |

## Build

Requires Rust (rustup) and `maturin`:

```bash
# Install rustup once
winget install Rustlang.Rustup        # Windows
# or: brew install rustup-init && rustup-init  (macOS)
# or: curl -sSf https://sh.rustup.rs | sh      (Linux)

rustup default stable
pip install maturin   # already in mercury's .venv

cd mercury-fast/
maturin develop --release
```

After install, `import mercury_fast` becomes a real native module. Mercury's
production code wraps it in a try/except — if rustc isn't available, the
pure-Python `mercury_fast_compat.py` shim runs.

## Profile to confirm wins

```bash
# Baseline (pure Python)
py-spy record -o flame_python.svg -- python -m mercury chat --no-startup-msg \
    -z "summarise: $(cat README.md)"

# After installing mercury_fast
py-spy record -o flame_rust.svg -- python -m mercury chat --no-startup-msg \
    -z "summarise: $(cat README.md)"
```

Diff the flame graphs in a browser — `parse_sse_event`, `count_tokens_cl100k`,
and `redact_secrets` should disappear from the top of the stack.

## Roadmap

The crate is intentionally small. As the hot-loop list grows, add functions
under one of these categories:

1. **Streaming + parsing** — anything that runs once per token chunk
2. **Token counting** — anything that runs in the compressor's per-message loop
3. **String / JSON shape transforms** — bulk scans across tool-call args / tool results

Don't lift agent loop logic, LLM client code, or anything async into Rust —
PyO3's GIL-release boundary is already the right shape, and Python is the
right tool there.
