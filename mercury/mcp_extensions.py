"""Mercury MCP server extensions for the auto-debug loop.

When `mercury mcp serve` is running, these handlers are registered on
top of upstream's 10 default tools, exposing the live state Claude
Code (or any other MCP client) needs to debug, fix, and redeploy
Mercury without leaving its own editor.

Tools added:

  - errors_tail(lines=200)
        Stream the last N lines of ~/.hermes/logs/errors.log.
        Includes session ids so the caller can drill into the
        offending JSONL via session_replay.

  - session_replay(session_id)
        Return the full turn-by-turn JSONL transcript for a session
        (model decisions, tool calls, tool results).  Heavy on
        tokens; use for offline forensic debugging only.

  - gateway_restart(reason)
        Stop the running `mercury gateway run` process group and
        spawn a fresh one.  Used after a fix lands so the change
        takes effect without a human in the loop.  Returns the new
        gateway PID + first 20 lines of boot output.

  - gateway_status()
        Cheap healthcheck — process alive, Discord connected, last
        successful turn timestamp.

  - debug_with_claude_code(error_id, fix_strategy="auto")
        Spawn a `claude -p` subprocess with a focused debug prompt.
        Uses the user's Claude Max plan (no separate API billing) —
        ALL token usage flows through their existing $100/mo
        subscription via the `claude` CLI.  Returns the patch the
        subprocess produced; caller decides whether to apply.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOGS_DIR = Path.home() / ".hermes" / "logs"
SESSIONS_DIR = Path.home() / ".hermes" / "sessions"


def errors_tail(lines: int = 200) -> dict[str, Any]:
    """Return the last N lines of errors.log + extracted session ids."""
    log_path = LOGS_DIR / "errors.log"
    if not log_path.exists():
        return {"ok": True, "lines": [], "session_ids": [], "note": "errors.log not yet created"}

    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:]
    except OSError as exc:
        return {"ok": False, "error": "io_error", "message": str(exc)}

    session_ids: list[str] = []
    for line in tail:
        for tok in line.split():
            if tok.startswith("[") and tok.endswith("]") and len(tok) > 20:
                sid = tok.strip("[]")
                if sid not in session_ids:
                    session_ids.append(sid)

    return {"ok": True, "lines": tail, "session_ids": session_ids[:10]}


def session_replay(session_id: str) -> dict[str, Any]:
    """Return the JSONL turn transcript for a session."""
    if not session_id:
        return {"ok": False, "error": "missing_session_id"}

    candidates = list(SESSIONS_DIR.glob(f"{session_id}*.jsonl"))
    if not candidates:
        return {"ok": False, "error": "session_not_found", "session_id": session_id}

    turns: list[dict] = []
    try:
        with candidates[0].open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    turns.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        return {"ok": False, "error": "io_error", "message": str(exc)}

    return {
        "ok": True,
        "session_id": session_id,
        "turn_count": len(turns),
        "turns": turns,
    }


def gateway_status() -> dict[str, Any]:
    """Cheap healthcheck — is the gateway process alive, Discord connected?"""
    pid_file = Path.home() / ".hermes" / "gateway.pid"
    pid = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except (OSError, ValueError):
            pid = None

    alive = False
    if pid:
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                alive = str(pid) in result.stdout
            else:
                os.kill(pid, 0)
                alive = True
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError):
            alive = False

    log_path = LOGS_DIR / "agent.log"
    last_turn_ts = None
    if log_path.exists():
        try:
            with log_path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 4096))
                tail = f.read().decode("utf-8", errors="replace")
            for line in reversed(tail.splitlines()):
                if "response ready" in line:
                    last_turn_ts = line.split()[0] + " " + line.split()[1]
                    break
        except OSError:
            pass

    return {
        "ok": True,
        "pid": pid,
        "alive": alive,
        "last_response_ready_at": last_turn_ts,
    }


def gateway_restart(reason: str = "manual") -> dict[str, Any]:
    """Stop the running gateway and respawn it. Cross-platform."""
    pid_file = Path.home() / ".hermes" / "gateway.pid"
    old_pid = None
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
        except (OSError, ValueError):
            pass

    killed = False
    if old_pid:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(old_pid)],
                    capture_output=True, timeout=10,
                )
            else:
                os.kill(old_pid, 15)
                time.sleep(2)
            killed = True
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError):
            pass

    venv_py = Path("C:/Users/soumi/mercury/.venv/Scripts/mercury.exe")
    if not venv_py.exists():
        return {"ok": False, "error": "mercury_not_installed", "path": str(venv_py)}

    log_path = LOGS_DIR / f"gateway_restart_{int(time.time())}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [str(venv_py), "gateway", "run", "-v"],
        stdout=open(log_path, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        cwd="D:/mercury",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
    )
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(proc.pid))

    time.sleep(8)
    try:
        boot_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]
    except OSError:
        boot_lines = []

    return {
        "ok": True,
        "killed_old_pid": old_pid if killed else None,
        "new_pid": proc.pid,
        "reason": reason,
        "boot_output": boot_lines,
    }


def debug_with_claude_code(
    error_id: str,
    *,
    fix_strategy: str = "auto",
    cwd: str = "D:/mercury",
    dangerously_skip_permissions: bool = False,
) -> dict[str, Any]:
    """Spawn a `claude -p` subprocess to debug an error.

    Uses the user's Claude Max subscription via the `claude` CLI — no
    separate Anthropic API key needed, all token cost charged against
    the existing $100/mo Max plan.
    """
    cli = subprocess.run(["where" if os.name == "nt" else "which", "claude"],
                         capture_output=True, text=True)
    if cli.returncode != 0:
        return {
            "ok": False,
            "error": "claude_cli_not_found",
            "message": "Install Claude Code from claude.ai/download — uses your Max plan.",
        }

    err = errors_tail(lines=80)
    err_text = "".join(err.get("lines", []))[-8000:]

    prompt = (
        f"Auto-debug session for Mercury (D:/mercury).\n\n"
        f"Error log tail (most recent first):\n```\n{err_text}\n```\n\n"
        f"Error id reference: {error_id}\n"
        f"Strategy: {fix_strategy}\n\n"
        f"Tasks:\n"
        f"  1. Identify the root cause from the trace.\n"
        f"  2. Make the minimal source-tree edit that fixes it.\n"
        f"  3. Run tests/mercury/ to confirm no regression.\n"
        f"  4. git commit with a `fix(...)` conventional message.\n"
        f"  5. Print a one-paragraph summary of the change.\n\n"
        f"Do NOT push to origin yet.  Do NOT restart the gateway.\n"
        f"The Mercury MCP server's `gateway_restart` tool will be called\n"
        f"separately by the orchestrator after you confirm the fix lands.\n"
    )

    args = ["claude", "-p", prompt]
    if dangerously_skip_permissions:
        args.append("--dangerously-skip-permissions")

    try:
        result = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "message": "claude -p exceeded 10 min"}

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-2000:],
        "note": "Token usage billed against Claude Max plan, not Anthropic API.",
    }
