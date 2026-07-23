#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC_DIR="${SCRIPT_DIR}/systemd"
UNIT_DST_DIR="${HOME}/.config/systemd/user"

UNITS=(
  pond-scrape.service
  pond-scrape.timer
  pond-weather.service
  pond-weather.timer
)

echo "[jwpc12] Installing pond user units"
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
systemctl --user enable --now pond-scrape.timer
systemctl --user enable --now pond-weather.timer

echo "Verifying timers"
systemctl --user list-timers --all | grep -E 'pond-scrape\.timer|pond-weather\.timer' || {
  echo "Error: expected pond timers not found" >&2
  exit 1
}

systemctl --user status pond-scrape.timer pond-weather.timer --no-pager

echo "Recent service logs"
journalctl --user -u pond-scrape.service -n 30 --no-pager || true
journalctl --user -u pond-weather.service -n 30 --no-pager || true

LINGER_VALUE="$(loginctl show-user "${USER}" -p Linger --value 2>/dev/null || echo unknown)"
if [[ "${LINGER_VALUE}" != "yes" ]]; then
  echo
  echo "Linger is not enabled for ${USER} (current: ${LINGER_VALUE})."
  echo "For timers to continue when logged out, run once as admin:"
  echo "  sudo loginctl enable-linger ${USER}"
else
  echo "Linger is enabled for ${USER}."
fi

echo "[jwpc12] User-unit deployment complete"
