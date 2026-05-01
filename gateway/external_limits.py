"""External-traffic rate limiting, daily cap, and kill switch.

Single source of truth for "is this external request allowed?". Used by
the public web endpoint (`/api/chat`) and the Discord adapter when the
sender is not the operator.

The state is held in-memory per gateway process — restarting the
gateway clears the per-minute / per-hour windows but preserves the
daily counter (which is keyed by UTC date and computed from the
external request log). The kill switch is persisted to
`~/.mercury/config.yaml` so a restart doesn't accidentally reopen
public traffic.
"""

from __future__ import annotations

import ipaddress
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    YAML_AVAILABLE = False


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "web": {
        "per_minute": 5,
        "per_hour": 30,
        "allowlist_cidrs": ["127.0.0.1/32"],
    },
    "discord": {
        "per_minute": 5,
        "per_hour": 30,
    },
    "operators_discord": [],
    "daily_cap": 1000,
    "daily_cap_message": "I've hit my daily limit — back tomorrow.",
    "kill_switch_message": (
        "Snowy is paused for maintenance.  External requests are off until "
        "the operator flips them back on."
    ),
    "status_webhook_url": "",
}


@dataclass
class CheckResult:
    allowed: bool
    reason: str = ""
    retry_after: Optional[float] = None
    message: str = ""


@dataclass
class _Window:
    timestamps: Deque[float] = field(default_factory=deque)


def _config_path() -> Path:
    home = Path(os.path.expanduser("~")) / ".mercury"
    return home / "config.yaml"


def _now() -> float:
    return time.time()


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ExternalLimits:
    """In-memory rate limiter + kill switch + daily cap."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._lock = threading.RLock()
        self._cfg = self._merge_defaults(config or {})
        self._owner_ids: List[str] = self._load_owner_ids()

        self._buckets: Dict[str, _Window] = {}
        self._daily_count: int = 0
        self._daily_date: str = _utc_today()

    @staticmethod
    def _merge_defaults(user: Dict[str, Any]) -> Dict[str, Any]:
        merged = {**DEFAULT_CONFIG, **(user or {})}
        merged["web"] = {**DEFAULT_CONFIG["web"], **(user.get("web") or {})}
        merged["discord"] = {**DEFAULT_CONFIG["discord"], **(user.get("discord") or {})}
        return merged

    @staticmethod
    def _load_owner_ids() -> List[str]:
        raw = os.environ.get("DISCORD_OWNER_IDS", "").strip()
        if not raw:
            return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    @classmethod
    def from_disk(cls) -> "ExternalLimits":
        """Load `external_limits` section from `~/.mercury/config.yaml`."""
        path = _config_path()
        cfg: Dict[str, Any] = {}
        if YAML_AVAILABLE and path.exists():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                cfg = data.get("external_limits") or {}
            except Exception:
                cfg = {}
        return cls(cfg)

    # ------------------------------------------------------------------
    # Properties + state
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        with self._lock:
            return bool(self._cfg.get("enabled", True))

    @property
    def daily_used(self) -> int:
        with self._lock:
            self._maybe_roll_daily()
            return self._daily_count

    @property
    def daily_cap(self) -> int:
        return int(self._cfg.get("daily_cap", 1000))

    @property
    def kill_switch_message(self) -> str:
        return str(self._cfg.get("kill_switch_message") or DEFAULT_CONFIG["kill_switch_message"])

    @property
    def daily_cap_message(self) -> str:
        return str(self._cfg.get("daily_cap_message") or DEFAULT_CONFIG["daily_cap_message"])

    @property
    def status_webhook_url(self) -> str:
        return str(self._cfg.get("status_webhook_url") or "").strip()

    def is_owner_discord(self, user_id: str) -> bool:
        if not user_id:
            return False
        if user_id in self._owner_ids:
            return True
        ops = [str(x) for x in (self._cfg.get("operators_discord") or [])]
        return user_id in ops

    def _maybe_roll_daily(self) -> None:
        today = _utc_today()
        if today != self._daily_date:
            self._daily_date = today
            self._daily_count = 0

    # ------------------------------------------------------------------
    # The actual check
    # ------------------------------------------------------------------

    def check(self, surface: str, identity: str) -> CheckResult:
        """Decide whether to admit a request.

        ``surface`` is "web" or "discord". ``identity`` is an IP for web
        and a Discord user-ID string for discord.
        """
        with self._lock:
            self._maybe_roll_daily()

            if not self.enabled:
                return CheckResult(False, reason="kill_switch", message=self.kill_switch_message)

            if self._daily_count >= self.daily_cap:
                return CheckResult(False, reason="daily_cap", message=self.daily_cap_message)

            if self._is_allowlisted(surface, identity):
                return CheckResult(True, reason="allowlisted")

            cfg = self._cfg.get(surface) or {}
            per_min = int(cfg.get("per_minute", 5))
            per_hour = int(cfg.get("per_hour", 30))

            bucket_key = f"{surface}:{identity}"
            bucket = self._buckets.setdefault(bucket_key, _Window())
            now = _now()
            # Drop timestamps older than 1h
            while bucket.timestamps and now - bucket.timestamps[0] > 3600:
                bucket.timestamps.popleft()

            in_last_min = sum(1 for t in bucket.timestamps if now - t <= 60)
            in_last_hour = len(bucket.timestamps)

            if in_last_min >= per_min:
                oldest_in_min = next((t for t in bucket.timestamps if now - t <= 60), now)
                retry = max(1.0, 60 - (now - oldest_in_min))
                return CheckResult(
                    False,
                    reason="rate_minute",
                    retry_after=retry,
                    message=f"Easy — try again in {int(retry)}s.",
                )
            if in_last_hour >= per_hour:
                oldest = bucket.timestamps[0] if bucket.timestamps else now
                retry = max(60.0, 3600 - (now - oldest))
                return CheckResult(
                    False,
                    reason="rate_hour",
                    retry_after=retry,
                    message=f"Hourly limit reached.  Try again in {int(retry / 60)}m.",
                )

            bucket.timestamps.append(now)
            self._daily_count += 1
            return CheckResult(True, reason="ok")

    def _is_allowlisted(self, surface: str, identity: str) -> bool:
        if surface == "web":
            cidrs = (self._cfg.get("web") or {}).get("allowlist_cidrs") or []
            try:
                ip = ipaddress.ip_address(identity)
            except ValueError:
                return False
            for cidr in cidrs:
                try:
                    if ip in ipaddress.ip_network(cidr, strict=False):
                        return True
                except ValueError:
                    continue
            return False
        if surface == "discord":
            return self.is_owner_discord(identity)
        return False

    # ------------------------------------------------------------------
    # Kill switch — persists to ~/.mercury/config.yaml
    # ------------------------------------------------------------------

    def set_enabled(self, value: bool) -> bool:
        with self._lock:
            self._cfg["enabled"] = bool(value)
            self._persist_enabled(bool(value))
            return self._cfg["enabled"]

    def _persist_enabled(self, value: bool) -> None:
        if not YAML_AVAILABLE:
            return
        path = _config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, Any] = {}
            if path.exists():
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = {}
            section = data.get("external_limits") or {}
            section["enabled"] = value
            data["external_limits"] = section
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        except Exception:
            pass


_singleton_lock = threading.Lock()
_singleton: Optional[ExternalLimits] = None


def get_external_limits() -> ExternalLimits:
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = ExternalLimits.from_disk()
    return _singleton


def reset_external_limits_for_tests() -> None:
    global _singleton
    with _singleton_lock:
        _singleton = None
