#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC_DIR="${SCRIPT_DIR}/systemd"
UNIT_DST_DIR="${HOME}/.config/systemd/user"

UNITS=(
  pond-web-api.service
  pond-apitest.service
  pond-apitest.timer
  pond-user-chart.service
  pond-user-chart.timer
)

echo "[gcweb1] Installing pond user units"
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

echo "Enabling and starting pond web API service"
systemctl --user enable --now pond-web-api.service

echo "Enabling and starting apitest/chart timers"
systemctl --user enable --now pond-apitest.timer
systemctl --user enable --now pond-user-chart.timer

echo "Verifying service"
systemctl --user status pond-web-api.service --no-pager || true
systemctl --user list-unit-files | grep -E '^pond-web-api\.service' || {
  echo "Error: expected pond-web-api service not found" >&2
  exit 1
}

echo "Recent service logs"
journalctl --user -u pond-web-api.service -n 30 --no-pager || true
journalctl --user -u pond-apitest.service -n 10 --no-pager || true
journalctl --user -u pond-user-chart.service -n 10 --no-pager || true

LINGER_VALUE="$(loginctl show-user "${USER}" -p Linger --value 2>/dev/null || echo unknown)"
if [[ "${LINGER_VALUE}" != "yes" ]]; then
  echo
  echo "Linger is not enabled for ${USER} (current: ${LINGER_VALUE})."
  echo "For services to continue when logged out, run once as admin:"
  echo "  sudo loginctl enable-linger ${USER}"
else
  echo "Linger is enabled for ${USER}."
fi

echo "[gcweb1] User-unit deployment complete"