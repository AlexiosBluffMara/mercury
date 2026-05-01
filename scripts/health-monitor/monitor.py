"""Cron-driven health probe for the rtk-* stack.

Runs every minute. For each service:
  1. Probe the relevant health endpoint.
  2. If unhealthy: attempt ``service_control.restart()``.
  3. After a 30-second grace period, re-probe.
  4. If still unhealthy, post an alert to the Discord webhook
     ``MERCURY_ALERT_WEBHOOK_URL``.

Auto-recovery + alert-only-on-failure means routine flaps are silent.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Make the repo's scripts/ dir importable so we can reuse rtk_tui.service_control
SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from rtk_tui import health_probes  # noqa: E402
from rtk_tui.service_control import ServiceController  # noqa: E402

GRACE_SECONDS = 30
WEBHOOK_ENV = "MERCURY_ALERT_WEBHOOK_URL"


@dataclass
class CheckResult:
    service: str
    healthy: bool
    detail: str


def check_cloudflared() -> CheckResult:
    info = health_probes.sync_tunnel()
    return CheckResult(
        service="rtk-cloudflared",
        healthy=info.healthy,
        detail=f"connections={info.connections} {info.detail}".strip(),
    )


def check_cortex() -> CheckResult:
    h = health_probes.sync_http(f"{health_probes.CORTEX_URL}/api/health")
    return CheckResult(
        service="rtk-cortex-webapp",
        healthy=h.ok,
        detail=h.detail or (f"HTTP {h.status_code}" if h.status_code else "unreachable"),
    )


def check_mercury() -> CheckResult:
    h = health_probes.sync_http(f"{health_probes.MERCURY_URL}/api/health")
    return CheckResult(
        service="rtk-mercury-gateway",
        healthy=h.ok,
        detail=h.detail or (f"HTTP {h.status_code}" if h.status_code else "unreachable"),
    )


CHECKS = (check_cloudflared, check_cortex, check_mercury)


def alert_discord(content: str) -> None:
    url = os.environ.get(WEBHOOK_ENV, "").strip()
    if not url:
        # Webhook not configured — log to stderr so cron mail / journald can pick it up
        sys.stderr.write(f"[monitor] (no {WEBHOOK_ENV} configured) {content}\n")
        return

    body = json.dumps({"content": content[:1900]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.URLError, TimeoutError) as exc:
        sys.stderr.write(f"[monitor] webhook post failed: {exc}\n")


def main() -> int:
    controller = ServiceController()
    failures: list[CheckResult] = []

    for check in CHECKS:
        result = check()
        if result.healthy:
            print(f"[monitor] {result.service}: OK ({result.detail})")
            continue

        print(f"[monitor] {result.service}: FAIL ({result.detail}) — attempting restart")
        ok, msg = controller.restart(result.service)
        print(f"[monitor]   restart returned ok={ok} msg={msg}")

        time.sleep(GRACE_SECONDS)

        recheck = check()
        if recheck.healthy:
            print(f"[monitor] {result.service}: recovered after restart")
        else:
            failures.append(recheck)
            alert_discord(
                f":rotating_light: **{recheck.service}** unhealthy and auto-restart failed.\n"
                f"detail: `{recheck.detail}`\n"
                f"restart attempt: ok={ok} msg=`{msg}`"
            )

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
