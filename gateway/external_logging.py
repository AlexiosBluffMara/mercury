"""Per-day JSONL log of external Mercury requests.

One file per UTC date at `~/.mercury/logs/external/YYYY-MM-DD.jsonl`,
one event per line. Used for cost / abuse tracking on the public web
endpoint and the Discord bot.

Records are intentionally minimal — no full prompts, no responses —
just enough to triage abuse and compute daily totals.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_PROMPT_PREFIX_LEN = 80
_lock = threading.Lock()


def _logs_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".mercury" / "logs" / "external"


def _today_path() -> Path:
    d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _logs_dir() / f"{d}.jsonl"


def log_external_request(
    *,
    surface: str,
    user: str,
    prompt: str,
    latency_ms: Optional[float] = None,
    model: Optional[str] = None,
    outcome: str = "ok",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Append one record to today's external log.

    Never raises — logging must not block the hot path. Failures are
    swallowed (the file may be locked, the disk full, etc.).
    """
    try:
        record: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "surface": surface,
            "user": user,
            "prompt_prefix": (prompt or "")[:_PROMPT_PREFIX_LEN],
            "outcome": outcome,
        }
        if latency_ms is not None:
            record["latency_ms"] = round(float(latency_ms), 1)
        if model:
            record["model"] = model
        if extra:
            for k, v in extra.items():
                if k not in record:
                    record[k] = v

        path = _today_path()
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        return


class StopWatch:
    """Tiny context-manager helper for timing a block in milliseconds."""

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self.elapsed_ms = 0.0

    def __enter__(self) -> "StopWatch":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0
