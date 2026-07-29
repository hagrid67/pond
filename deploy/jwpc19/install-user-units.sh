#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC_DIR="${SCRIPT_DIR}/systemd"
UNIT_DST_DIR="${HOME}/.config/systemd/user"

UNITS=(
  pond-dev-sync.service
  pond-dev-sync.timer
  pond-web-api.service
  pond-user-chart.service
  pond-user-chart.timer
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

echo "Enabling and starting timers"
systemctl --user enable --now pond-dev-sync.timer pond-user-chart.timer

echo "Enabling and restarting dev web API service"
systemctl --user enable pond-web-api.service
systemctl --user restart pond-web-api.service

echo "Verifying timer"
systemctl --user list-timers --all | grep -E 'pond-dev-sync\.timer|pond-user-chart\.timer' || {
  echo "Error: expected jwpc19 timers not found" >&2
  exit 1
}

systemctl --user status pond-dev-sync.timer pond-dev-sync.service pond-user-chart.timer pond-user-chart.service pond-web-api.service --no-pager

echo "Recent service logs"
journalctl --user -u pond-dev-sync.service -n 30 --no-pager || true
journalctl --user -u pond-user-chart.service -n 20 --no-pager || true
journalctl --user -u pond-web-api.service -n 20 --no-pager || true

echo
echo "Migration note: if old pond-rsync-data user units are installed, remove them with:"
echo "  ${SCRIPT_DIR}/remove-old-units.sh"

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
