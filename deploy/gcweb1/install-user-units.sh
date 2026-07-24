#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC_DIR="${SCRIPT_DIR}/systemd"
UNIT_DST_DIR="${HOME}/.config/systemd/user"

UNITS=(
  pond-pondupdate-api.service
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

echo "Enabling and starting pond update API service"
systemctl --user enable --now pond-pondupdate-api.service

echo "Verifying service"
systemctl --user status pond-pondupdate-api.service --no-pager || true
systemctl --user list-unit-files | grep -E '^pond-pondupdate-api\.service' || {
  echo "Error: expected pond-pondupdate-api service not found" >&2
  exit 1
}

echo "Recent service logs"
journalctl --user -u pond-pondupdate-api.service -n 30 --no-pager || true

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