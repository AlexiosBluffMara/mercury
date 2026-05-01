#!/usr/bin/env bash
# Install rtk-* user systemd units. Idempotent.
#
# Copies the .service files in this directory to ~/.config/systemd/user/,
# reloads the user daemon, then enables + starts each. Linger is enabled
# so services start at boot (not just at user login).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"

mkdir -p "${UNIT_DIR}"
mkdir -p "${HOME}/.cloudflared"
mkdir -p "${HOME}/.cortex/logs"
mkdir -p "${HOME}/.mercury/logs"

UNITS=(
    rtk-cloudflared.service
    rtk-cortex-webapp.service
    rtk-mercury-gateway.service
)

for unit in "${UNITS[@]}"; do
    src="${SCRIPT_DIR}/${unit}"
    dst="${UNIT_DIR}/${unit}"
    if ! cmp -s "${src}" "${dst}" 2>/dev/null; then
        echo "[install] copying ${unit}"
        cp "${src}" "${dst}"
    else
        echo "[install] ${unit} already up to date"
    fi
done

systemctl --user daemon-reload

for unit in "${UNITS[@]}"; do
    echo "[install] enabling + starting ${unit}"
    systemctl --user enable "${unit}"
    systemctl --user restart "${unit}" || true
done

# Boot-time start (only effective if the user ever needs services up
# without an interactive login -- e.g. server / HPC node).
if command -v loginctl >/dev/null 2>&1; then
    if ! loginctl show-user "${USER}" 2>/dev/null | grep -q '^Linger=yes'; then
        echo "[install] enabling lingering for ${USER} (allows services to run without an active session)"
        sudo loginctl enable-linger "${USER}" || \
            echo "  (could not enable linger -- services will start on next login instead)"
    fi
fi

echo
echo "=== Status ==="
for unit in "${UNITS[@]}"; do
    state=$(systemctl --user is-active "${unit}" 2>/dev/null || echo unknown)
    enabled=$(systemctl --user is-enabled "${unit}" 2>/dev/null || echo unknown)
    printf "  %-32s active=%-10s enabled=%s\n" "${unit}" "${state}" "${enabled}"
done

echo
echo "Tail a log live:"
echo "  journalctl --user -u rtk-mercury-gateway -f"
