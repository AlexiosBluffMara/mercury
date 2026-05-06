#!/usr/bin/env python3
"""openrouter_daily.py — Track and budget Mercury's free OpenRouter allocation.

Account has $20 in OpenRouter credits → 1000 :free model requests per day.
Goal: spend the full daily allocation on Mercury self-improvement work
(memo generation, log digests, test-case synthesis, model evals) without
EVER touching the paid credit pool.

Usage:
    # Check remaining daily budget (reads/writes ~/.mercury/openrouter_daily_quota.json)
    python openrouter_daily.py status

    # Reserve N requests for a planned workload; refuses if budget would go negative
    python openrouter_daily.py reserve --count 50 --task "nightly-log-digest"

    # Record an actually-completed call (decrement counters, record model used)
    python openrouter_daily.py record --model "google/gemma-4-26b-a4b-it:free" \\
                                     --tokens-in 234 --tokens-out 187 --task "nightly-log-digest"

    # Refresh remote credit balance and verify we haven't burned anything paid
    python openrouter_daily.py audit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

QUOTA_FILE = Path.home() / ".mercury" / "openrouter_daily_quota.json"
DAILY_FREE_CAP = 1000   # OpenRouter limit when balance is $10+
PAID_TRIPWIRE_USD = 0.01  # any paid spend over this triggers an alert


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load() -> dict:
    if not QUOTA_FILE.exists():
        return {"date": _today(), "free_used": 0, "paid_usd": 0.0, "tasks": {}}
    data = json.loads(QUOTA_FILE.read_text())
    if data.get("date") != _today():
        # Roll over to a new day, archive yesterday
        archive_dir = QUOTA_FILE.parent / "openrouter_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / f"{data['date']}.json").write_text(json.dumps(data, indent=2))
        data = {"date": _today(), "free_used": 0, "paid_usd": 0.0, "tasks": {}}
    return data


def _save(data: dict) -> None:
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(data, indent=2))


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        env_path = Path.home() / ".mercury" / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        sys.exit("OPENROUTER_API_KEY not set in env or ~/.mercury/.env")
    return key


def _credits() -> dict:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {_api_key()}"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["data"]


def status() -> int:
    data = _load()
    remaining = DAILY_FREE_CAP - data["free_used"]
    print(f"OpenRouter daily quota — {data['date']}")
    print(f"  free used:        {data['free_used']:>5} / {DAILY_FREE_CAP}")
    print(f"  free remaining:   {remaining:>5}")
    print(f"  paid usd today:   ${data['paid_usd']:.4f}")
    if data["tasks"]:
        print(f"  by task:")
        for task, n in sorted(data["tasks"].items(), key=lambda x: -x[1]):
            print(f"    {n:>4}  {task}")
    return 0 if remaining > 0 else 1


def reserve(count: int, task: str) -> int:
    data = _load()
    if data["free_used"] + count > DAILY_FREE_CAP:
        print(
            f"REFUSE: need {count} but only "
            f"{DAILY_FREE_CAP - data['free_used']} free reqs left today",
            file=sys.stderr,
        )
        return 1
    print(f"OK reserved {count} for '{task}' (used {data['free_used']}/{DAILY_FREE_CAP})")
    return 0


def record(model: str, tokens_in: int, tokens_out: int, task: str, cost_usd: float = 0.0) -> int:
    data = _load()
    if not model.endswith(":free") and cost_usd > PAID_TRIPWIRE_USD:
        print(
            f"WARN: paid call detected — model={model}, cost=${cost_usd:.4f}. "
            f"Mercury config should prevent this.",
            file=sys.stderr,
        )
        data["paid_usd"] = round(data["paid_usd"] + cost_usd, 6)
    if model.endswith(":free"):
        data["free_used"] += 1
    data["tasks"][task] = data["tasks"].get(task, 0) + 1
    _save(data)
    return 0


def audit() -> int:
    data = _load()
    remote = _credits()
    print(f"Local tracking: free_used={data['free_used']} paid_today=${data['paid_usd']:.4f}")
    print(f"Remote balance: total={remote['total_credits']} usage={remote['total_usage']}")
    if remote["total_usage"] - data["paid_usd"] > 0.05:
        print("ALERT: remote usage exceeds local tracking by >$0.05", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_res = sub.add_parser("reserve"); p_res.add_argument("--count", type=int, required=True); p_res.add_argument("--task", required=True)
    p_rec = sub.add_parser("record"); p_rec.add_argument("--model", required=True); p_rec.add_argument("--tokens-in", type=int, default=0); p_rec.add_argument("--tokens-out", type=int, default=0); p_rec.add_argument("--task", required=True); p_rec.add_argument("--cost-usd", type=float, default=0.0)
    sub.add_parser("audit")
    args = p.parse_args()
    return {
        "status": status,
        "reserve": lambda: reserve(args.count, args.task),
        "record": lambda: record(args.model, args.tokens_in, args.tokens_out, args.task, args.cost_usd),
        "audit": audit,
    }[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())
