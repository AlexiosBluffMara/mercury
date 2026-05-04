"""profile_mercury.py — drive Mercury through the hot-path workload that the
Rust extension is designed to accelerate.

Usage (under py-spy):

    py-spy record -o flame.svg --rate 250 -- python scripts/profile_mercury.py

What it does:
  1. Loads the Mercury agent runtime (without spawning a chat).
  2. Replays a synthetic SSE stream chunk-by-chunk through the parser.
  3. Counts tokens on a corpus of mixed text (typical compressor workload).
  4. Redacts secrets across a tool-call argument blob.

This isolates the compute the Rust crate replaces, so the flame graph is
sharp instead of dominated by socket / LLM-API I/O.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Make sure mercury_fast (Rust) wins over the compat shim if installed
try:
    from mercury_fast import parse_sse_event, count_tokens_cl100k, redact_secrets
    BACKEND = "rust"
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mercury-fast" / "python"))
    from mercury_fast_compat import parse_sse_event, count_tokens_cl100k, redact_secrets
    BACKEND = "python"

print(f"[profile] backend = {BACKEND}", flush=True)

# ── 1. Synthetic SSE stream ──────────────────────────────────────────────────
# 5,000 OpenAI-style chunks. Real workloads see ~3-4k of these per scan.
_SSE_CHUNKS = [
    b'data: {"id":"chatcmpl-x","choices":[{"delta":{"content":"the visual cortex "}}]}\n',
    b'data: {"id":"chatcmpl-x","choices":[{"delta":{"content":"and motor regions "}}]}\n',
    b'data: {"id":"chatcmpl-x","choices":[{"delta":{"content":"engage when "}}]}\n',
    b'data: {"id":"chatcmpl-x","choices":[{"delta":{"content":"viewing this stimulus.\\n"}}]}\n',
    b':keep-alive\n',
    b'data: [DONE]\n',
]

# ── 2. Mixed-length text corpus for token counting ───────────────────────────
_CORPUS = [
    "Short prompt.",
    "A medium-length prompt with a few sentences. The compressor calls token "
    "count many times per turn, so this loop matters.",
    " ".join(["lorem ipsum dolor sit amet"] * 200),
    json.dumps({"role": "tool", "content": "{\"result\":\"ok\",\"data\":[1,2,3]}"}),
] * 250  # 1000 calls

# ── 3. Tool-arg blob with secrets to redact ──────────────────────────────────
_BLOB = """
The user accidentally pasted their API key sk-1234567890abcdefghij1234567890ZZ
and an Anthropic key sk-ant-1234567890abcdefghij1234567890ABCDE here.
Plus a bearer token in the header: Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456
GitHub PAT: ghp_abcdefghijklmnopqrstuvwxyz1234567890
AWS access: AKIAIOSFODNN7EXAMPLE
""" * 50


def main() -> None:
    rounds = 1500
    t0 = time.perf_counter()
    n_parsed = 0
    for _ in range(rounds):
        for c in _SSE_CHUNKS:
            ev = parse_sse_event(c)
            if ev is not None:
                n_parsed += 1
    t1 = time.perf_counter()
    print(f"[profile] sse_parse:    {n_parsed:>7d} events in {t1-t0:6.3f}s "
          f"= {n_parsed/(t1-t0):>8.0f} eps", flush=True)

    t0 = time.perf_counter()
    total_tokens = 0
    for s in _CORPUS:
        total_tokens += count_tokens_cl100k(s)
    t1 = time.perf_counter()
    print(f"[profile] tok_count:    {len(_CORPUS):>7d} strings in {t1-t0:6.3f}s "
          f"({total_tokens} tokens)", flush=True)

    t0 = time.perf_counter()
    for _ in range(800):
        redact_secrets(_BLOB)
    t1 = time.perf_counter()
    print(f"[profile] redact:       {800:>7d} blobs in {t1-t0:6.3f}s "
          f"({800 * len(_BLOB) / (t1-t0) / 1e6:.1f} MB/s)", flush=True)


if __name__ == "__main__":
    main()
