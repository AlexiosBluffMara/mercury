#!/usr/bin/env bash
# Install a per-user cron entry that runs monitor.py every minute.
# Idempotent: drops any existing rtk-health-monitor line before adding.

set -euo pipefail

PYTHON="${PYTHON:-${HOME}/mercury/.venv/bin/python}"
SCRIPT="${SCRIPT:-${HOME}/mercury/scripts/health-monitor/monitor.py}"
MARKER='# rtk-health-monitor'

if [[ ! -x "${PYTHON}" ]]; then
    echo "Python not found at ${PYTHON}. Set PYTHON=... before running."
    exit 1
fi
if [[ ! -f "${SCRIPT}" ]]; then
    echo "monitor.py not found at ${SCRIPT}. Set SCRIPT=... before running."
    exit 1
fi

# Pull current crontab (may not exist), strip our line, append the fresh one.
existing="$(crontab -l 2>/dev/null || true)"
filtered="$(printf '%s\n' "${existing}" | grep -v -F "${MARKER}" || true)"

new_entry="* * * * * ${PYTHON} ${SCRIPT} >> ${HOME}/.mercury/logs/health-monitor.log 2>&1 ${MARKER}"

mkdir -p "${HOME}/.mercury/logs"

{
    if [[ -n "${filtered}" ]]; then printf '%s\n' "${filtered}"; fi
    printf '%s\n' "${new_entry}"
} | crontab -

echo "[install-cron] installed: ${new_entry}"
crontab -l | grep -F "${MARKER}"
