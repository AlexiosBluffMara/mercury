"""Pure-Python fallbacks for mercury_fast — used when the Rust extension
hasn't been built (e.g. fresh clone, CI without rustc).

Anything in here MUST match the public surface of `mercury_fast` (the Rust
crate) so callers can do:

    try:
        from mercury_fast import parse_sse_event, count_tokens_cl100k, redact_secrets
    except ImportError:
        from mercury_fast_compat import parse_sse_event, count_tokens_cl100k, redact_secrets

Build the fast extension with:

    cd mercury-fast/
    maturin develop --release   # installs into the active venv
"""
from __future__ import annotations

import json
import re
from typing import Any

# ── 1. SSE / streaming chunk parser ─────────────────────────────────────────
_SSE_DATA = re.compile(r"^data:\s?(?P<payload>.*)$")


def parse_sse_event(line: bytes | str) -> Any:
    if isinstance(line, bytes):
        try:
            s = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"invalid utf-8 in sse line: {exc}") from exc
    else:
        s = line
    s = s.rstrip("\r\n")
    if not s or s.startswith(":"):
        return None
    m = _SSE_DATA.match(s)
    if not m:
        return None
    payload = m.group("payload")
    if payload == "[DONE]":
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"sse data not json: {exc}") from exc


# ── 2. Token counter wrapper ───────────────────────────────────────────────
_tiktoken = None


def count_tokens_cl100k(text: str) -> int:
    global _tiktoken
    if _tiktoken is None:
        try:
            import tiktoken
            _tiktoken = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            # Final fallback: rough word/char heuristic. Worse but never crashes.
            _tiktoken = "approx"
    if _tiktoken == "approx":
        return max(1, len(text) // 4)
    return len(_tiktoken.encode(text, disallowed_special=()))


# ── 3. Bulk redaction ──────────────────────────────────────────────────────
_REDACT = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),                 "sk-***REDACTED***"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),             "sk-ant-***REDACTED***"),
    (re.compile(r"sk-or-v1-[A-Za-z0-9]{32,}"),              "sk-or-***REDACTED***"),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"),                   "ghp_***REDACTED***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"),                       "AKIA***REDACTED***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{20,}"),   r"\1***REDACTED***"),
]


def redact_secrets(s: str) -> str:
    for pat, repl in _REDACT:
        s = pat.sub(repl, s)
    return s
