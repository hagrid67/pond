#!/usr/bin/env bash
set -euo pipefail

UNIT_DST_DIR="${HOME}/.config/systemd/user"
WANTS_DIR="${UNIT_DST_DIR}/timers.target.wants"
OLD_UNITS=(
  pond-rsync-data.timer
  pond-rsync-data.service
)

echo "[jwpc19] Removing deprecated pond-rsync-data user units"

for unit in "${OLD_UNITS[@]}"; do
  # Stop/reset in-memory units even when the unit file is already missing.
  systemctl --user stop "${unit}" 2>/dev/null || true
  systemctl --user disable "${unit}" 2>/dev/null || true
  systemctl --user reset-failed "${unit}" 2>/dev/null || true

  if [[ -f "${UNIT_DST_DIR}/${unit}" ]]; then
    rm -f "${UNIT_DST_DIR}/${unit}"
    echo "Removed ${UNIT_DST_DIR}/${unit}"
  fi

  if [[ -L "${WANTS_DIR}/${unit}" || -e "${WANTS_DIR}/${unit}" ]]; then
    rm -f "${WANTS_DIR}/${unit}"
    echo "Removed ${WANTS_DIR}/${unit}"
  fi
done

echo "Reloading user systemd"
systemctl --user daemon-reload

echo "Verifying deprecated timers are absent"
if systemctl --user list-timers --all | grep -E 'pond-rsync-data\.timer' >/dev/null 2>&1; then
  echo "Warning: pond-rsync-data.timer still appears in list-timers output" >&2
else
  echo "No pond-rsync-data timers found"
fi

echo "[jwpc19] Deprecated unit removal complete"
