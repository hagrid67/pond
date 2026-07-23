#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC_DIR="${SCRIPT_DIR}/systemd"
UNIT_DST_DIR="${HOME}/.config/systemd/user"

UNITS=(
  pond-rsync-data.service
  pond-rsync-data.timer
)

echo "[jwpc19] Installing pond user units"
mkdir -p "${UNIT_DST_DIR}"

for unit in "${UNITS[@]}"; do
  if [[ ! -f "${UNIT_SRC_DIR}/${unit}" ]]; then
    echo "Error: missing source unit ${UNIT_SRC_DIR}/${unit}" >&2
    exit 1
  fi
  install -m 0644 "${UNIT_SRC_DIR}/${unit}" "${UNIT_DST_DIR}/${unit}"
  echo "Installed ${unit}"
done

echo "Reloading user systemd"
systemctl --user daemon-reload

echo "Enabling and starting timer"
systemctl --user enable --now pond-rsync-data.timer

echo "Verifying timer"
systemctl --user list-timers --all | grep -E 'pond-rsync-data\.timer' || {
  echo "Error: expected pond-rsync-data timer not found" >&2
  exit 1
}

systemctl --user status pond-rsync-data.timer pond-rsync-data.service --no-pager

echo "Recent service logs"
journalctl --user -u pond-rsync-data.service -n 30 --no-pager || true

LINGER_VALUE="$(loginctl show-user "${USER}" -p Linger --value 2>/dev/null || echo unknown)"
if [[ "${LINGER_VALUE}" != "yes" ]]; then
  echo
  echo "Linger is not enabled for ${USER} (current: ${LINGER_VALUE})."
  echo "For timers to continue when logged out, run once as admin:"
  echo "  sudo loginctl enable-linger ${USER}"
else
  echo "Linger is enabled for ${USER}."
fi

echo "[jwpc19] User-unit deployment complete"
