"""Cross-platform service controller.

Wraps Windows (``nssm`` / ``sc.exe``) and Linux (``systemctl --user``) behind
a single ``ServiceController`` with ``start/stop/restart/status``.

The same module is imported by the TUI, the Discord ``/services`` command,
and the health monitor — so the recovery path is the same regardless of who
triggered it.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SERVICES = ("rtk-cloudflared", "rtk-cortex-webapp", "rtk-mercury-gateway")


def _user_home() -> Path:
    return Path(os.path.expanduser("~"))


@dataclass(frozen=True)
class LogPaths:
    """Where each service writes its logs."""

    out: Path
    err: Path | None  # cloudflared writes one combined log -> err is None


LOG_PATHS: dict[str, LogPaths] = {
    "rtk-cloudflared": LogPaths(
        out=_user_home() / ".cloudflared" / "service.log",
        err=None,
    ),
    "rtk-cortex-webapp": LogPaths(
        out=_user_home() / ".cortex" / "logs" / "webapp.out.log",
        err=_user_home() / ".cortex" / "logs" / "webapp.err.log",
    ),
    "rtk-mercury-gateway": LogPaths(
        out=_user_home() / ".mercury" / "logs" / "gateway.out.log",
        err=_user_home() / ".mercury" / "logs" / "gateway.err.log",
    ),
}


@dataclass
class ServiceStatus:
    name: str
    state: str            # "running" | "stopped" | "starting" | "stopping" | "errored" | "unknown"
    detail: str = ""      # optional one-line summary

    @property
    def is_running(self) -> bool:
        return self.state == "running"


class ServiceController:
    """Start / stop / restart / status for the rtk-* services."""

    def __init__(self) -> None:
        self.platform = platform.system()  # "Windows" / "Linux" / "Darwin"

    # -- public API ---------------------------------------------------------

    def list(self) -> list[str]:
        return list(SERVICES)

    def status(self, name: str) -> ServiceStatus:
        if self.platform == "Windows":
            return self._status_windows(name)
        return self._status_systemd(name)

    def start(self, name: str) -> tuple[bool, str]:
        return self._run_action(name, "start")

    def stop(self, name: str) -> tuple[bool, str]:
        return self._run_action(name, "stop")

    def restart(self, name: str) -> tuple[bool, str]:
        return self._run_action(name, "restart")

    def tail_log(self, name: str, *, lines: int = 50, stream: str = "out") -> str:
        """Return the last ``lines`` of the service log.

        ``stream`` is "out" or "err"; falls back to "out" if the requested
        stream doesn't exist (e.g. cloudflared's combined log).
        """
        paths = LOG_PATHS.get(name)
        if not paths:
            return f"(unknown service: {name})"
        path = paths.err if (stream == "err" and paths.err is not None) else paths.out
        if not path or not path.exists():
            return f"(no log file at {path})"
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                buf = f.readlines()
        except OSError as exc:
            return f"(error reading {path}: {exc})"
        return "".join(buf[-lines:])

    # -- internals ----------------------------------------------------------

    def _run_action(self, name: str, action: str) -> tuple[bool, str]:
        if name not in SERVICES:
            return False, f"unknown service: {name}"

        if self.platform == "Windows":
            cmd = self._windows_cmd_for(action, name)
        else:
            cmd = ["systemctl", "--user", action, name]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return False, f"{action} {name} failed: {exc}"

        ok = result.returncode == 0
        msg = (result.stdout or result.stderr or "").strip().splitlines()
        summary = msg[-1] if msg else f"exit={result.returncode}"
        return ok, summary

    def _windows_cmd_for(self, action: str, name: str) -> list[str]:
        # Prefer NSSM (handles auto-restart cleanly); fall back to sc.exe.
        nssm = shutil.which("nssm") or r"C:\Program Files\nssm\nssm.exe"
        if Path(nssm).exists():
            mapping = {"start": "start", "stop": "stop", "restart": "restart"}
            return [nssm, mapping[action], name]
        # sc.exe doesn't have "restart" -- callers should use stop+start.
        if action == "restart":
            return ["powershell", "-NoProfile", "-Command", f"Restart-Service -Name {name} -Force"]
        return ["sc.exe", action, name]

    def _status_windows(self, name: str) -> ServiceStatus:
        try:
            result = subprocess.run(
                ["sc.exe", "query", name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return ServiceStatus(name=name, state="unknown", detail=str(exc))

        if result.returncode != 0:
            return ServiceStatus(name=name, state="unknown", detail="not installed")

        lower = result.stdout.lower()
        if "running" in lower:
            state = "running"
        elif "stop_pending" in lower:
            state = "stopping"
        elif "start_pending" in lower:
            state = "starting"
        elif "stopped" in lower:
            state = "stopped"
        else:
            state = "unknown"
        return ServiceStatus(name=name, state=state)

    def _status_systemd(self, name: str) -> ServiceStatus:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return ServiceStatus(name=name, state="unknown", detail=str(exc))

        active = (result.stdout or "").strip()
        mapping = {
            "active": "running",
            "inactive": "stopped",
            "failed": "errored",
            "activating": "starting",
            "deactivating": "stopping",
        }
        return ServiceStatus(name=name, state=mapping.get(active, "unknown"), detail=active)
