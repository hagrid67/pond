#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"

SERVICES=(
  pond-dev-web-api.service
  pond-dev-sync.service
  pond-user-chart.service
)

TIMERS=(
  pond-dev-sync.timer
  pond-user-chart.timer
)

ALL_UNITS=("${SERVICES[@]}" "${TIMERS[@]}")

usage() {
  cat <<'EOF'
Usage: manage-pond-services.sh [start|stop|restart|status]

Manage all jwpc19 pond user units locally via systemd --user.
EOF
}

case "${ACTION}" in
  start)
    systemctl --user daemon-reload
    systemctl --user enable --now "${TIMERS[@]}"
    systemctl --user enable --now pond-dev-web-api.service
    ;;
  stop)
    systemctl --user stop "${TIMERS[@]}" || true
    systemctl --user stop "${SERVICES[@]}" || true
    ;;
  restart)
    systemctl --user daemon-reload
    systemctl --user restart pond-dev-web-api.service
    systemctl --user restart "${TIMERS[@]}"
    ;;
  status)
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Error: unknown action '${ACTION}'" >&2
    usage
    exit 1
    ;;
esac

systemctl --user status "${ALL_UNITS[@]}" --no-pager
