"""Tailscale helpers for Mercury.

The WebUI binds to localhost and is exposed to the tailnet via
`tailscale serve`.  Tailscale injects `Tailscale-User-Login` and
`Tailscale-User-Name` headers on every request, so Mercury treats
those as the auth identity — no separate password layer.

When the user runs Mercury on a machine without Tailscale installed,
all helpers degrade to None / False rather than raising; the WebUI
is then reachable on localhost only.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TailnetIdentity:
    login: str
    name: str
    profile_picture: str | None = None


def is_installed() -> bool:
    return shutil.which("tailscale") is not None


def status() -> dict | None:
    if not is_installed():
        return None
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def is_running() -> bool:
    s = status()
    return bool(s and s.get("BackendState") == "Running")


def hostname() -> str | None:
    s = status()
    if not s:
        return None
    self_node = s.get("Self") or {}
    return self_node.get("HostName") or self_node.get("DNSName", "").split(".")[0] or None


def magic_dns_name() -> str | None:
    s = status()
    if not s:
        return None
    self_node = s.get("Self") or {}
    dns = self_node.get("DNSName", "").rstrip(".")
    return dns or None


def tailnet_ip() -> str | None:
    s = status()
    if not s:
        return None
    self_node = s.get("Self") or {}
    ips = self_node.get("TailscaleIPs") or []
    for ip in ips:
        if ":" not in ip:
            return ip
    return ips[0] if ips else None


def webui_url(port: int = 8765, https: bool = False) -> str | None:
    name = magic_dns_name()
    if not name:
        return None
    scheme = "https" if https else "http"
    return f"{scheme}://{name}:{port}"


def extract_identity(headers: dict | Iterable[tuple[str, str]]) -> TailnetIdentity | None:
    """Read Tailscale identity from request headers.

    `headers` accepts either a dict (Starlette/FastAPI request.headers
    behaves dict-like) or an iterable of (name, value) tuples.
    """
    if isinstance(headers, dict):
        get = lambda k: headers.get(k.lower()) or headers.get(k)
    else:
        lookup = {k.lower(): v for k, v in headers}
        get = lambda k: lookup.get(k.lower())

    login = get("Tailscale-User-Login")
    if not login:
        return None
    return TailnetIdentity(
        login=login,
        name=get("Tailscale-User-Name") or login,
        profile_picture=get("Tailscale-User-Profile-Pic"),
    )


def serve_command(port: int = 8765, https: bool = True) -> list[str]:
    """Build the `tailscale serve` argv to expose the local WebUI.

    Run this on the host once.  `tailscale serve` persists the config.
    """
    if https:
        return ["tailscale", "serve", "--bg", "--https=443", f"http://localhost:{port}"]
    return ["tailscale", "serve", "--bg", f"--tcp={port}", f"tcp://localhost:{port}"]
