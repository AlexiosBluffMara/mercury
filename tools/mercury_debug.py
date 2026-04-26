"""Mercury auto-debug tools — register the mcp_extensions handlers as
agent-callable tools.  The agent can now `errors_tail`, `session_replay`,
`gateway_status`, `gateway_restart`, and `debug_with_claude_code` itself
when the user asks "fix what just broke" or via the auto-debug cron.

All token usage in `debug_with_claude_code` flows through the user's
existing Claude Max plan via the `claude` CLI subprocess — no separate
Anthropic API key, no per-token billing.
"""
from __future__ import annotations

from typing import Any

from mercury.mcp_extensions import (
    debug_with_claude_code,
    errors_tail,
    gateway_restart,
    gateway_status,
    session_replay,
)


def _wrap_errors_tail(args: dict | None = None, **_kw: Any) -> dict:
    args = args or {}
    return errors_tail(lines=int(args.get("lines", 200)))


def _wrap_session_replay(args: dict | None = None, **_kw: Any) -> dict:
    args = args or {}
    return session_replay(session_id=str(args.get("session_id") or "").strip())


def _wrap_gateway_status(_args: dict | None = None, **_kw: Any) -> dict:
    return gateway_status()


def _wrap_gateway_restart(args: dict | None = None, **_kw: Any) -> dict:
    args = args or {}
    return gateway_restart(reason=str(args.get("reason") or "manual"))


def _wrap_debug_with_claude_code(args: dict | None = None, **_kw: Any) -> dict:
    args = args or {}
    return debug_with_claude_code(
        error_id=str(args.get("error_id") or ""),
        fix_strategy=str(args.get("fix_strategy") or "auto"),
        cwd=str(args.get("cwd") or "D:/mercury"),
        dangerously_skip_permissions=bool(args.get("dangerously_skip_permissions", False)),
    )


from tools.registry import registry  # noqa: E402

registry.register(
    name="errors_tail",
    toolset="debug",
    schema={
        "name": "errors_tail",
        "description": "Tail the last N lines of Mercury's errors.log and extract any session ids found.  Use this first when the user asks 'what just broke' or before invoking debug_with_claude_code.",
        "parameters": {
            "type": "object",
            "properties": {
                "lines": {"type": "integer", "default": 200, "description": "How many recent log lines to scan"},
            },
        },
    },
    handler=_wrap_errors_tail,
    is_async=False,
    description="Tail errors.log",
    emoji="📜",
    max_result_size_chars=20000,
)

registry.register(
    name="session_replay",
    toolset="debug",
    schema={
        "name": "session_replay",
        "description": "Return the full turn-by-turn JSONL transcript of a Mercury session, including model decisions, tool calls, and tool results.  Get the session_id from errors_tail first.",
        "parameters": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    },
    handler=_wrap_session_replay,
    is_async=False,
    description="Full session transcript",
    emoji="🔍",
    max_result_size_chars=80000,
)

registry.register(
    name="gateway_status",
    toolset="debug",
    schema={
        "name": "gateway_status",
        "description": "Quick healthcheck of Mercury's gateway: is the process alive, when was the last successful turn, what's the PID.",
        "parameters": {"type": "object", "properties": {}},
    },
    handler=_wrap_gateway_status,
    is_async=False,
    description="Gateway health",
    emoji="💓",
    max_result_size_chars=2000,
)

registry.register(
    name="gateway_restart",
    toolset="debug",
    schema={
        "name": "gateway_restart",
        "description": "Stop Mercury's running gateway process and respawn a fresh one.  Use after debug_with_claude_code lands a fix and the source tree is committed.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string", "default": "manual"}},
        },
    },
    handler=_wrap_gateway_restart,
    is_async=False,
    description="Gateway restart",
    emoji="🔁",
    max_result_size_chars=8000,
)

registry.register(
    name="debug_with_claude_code",
    toolset="debug",
    schema={
        "name": "debug_with_claude_code",
        "description": "Spawn a `claude -p` subprocess to debug an error.  Reads errors.log + session transcripts, edits source, runs tests, commits.  All token cost flows through the user's Claude Max plan via the claude CLI — no separate API billing.  Pair with gateway_restart after the fix lands.",
        "parameters": {
            "type": "object",
            "properties": {
                "error_id": {"type": "string", "description": "Optional reference id from errors_tail"},
                "fix_strategy": {"type": "string", "default": "auto", "description": "auto | conservative | aggressive"},
                "cwd": {"type": "string", "default": "D:/mercury"},
                "dangerously_skip_permissions": {"type": "boolean", "default": False},
            },
        },
    },
    handler=_wrap_debug_with_claude_code,
    is_async=False,
    description="Auto-debug via Claude Code",
    emoji="🛠️",
    max_result_size_chars=12000,
)
