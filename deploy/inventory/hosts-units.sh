#!/usr/bin/env bash

# Host inventory for deploy orchestration.
# Outputs are space-delimited where multiple values are returned.

host_repo_subpath() {
  # All current hosts use the same relative repo path under $HOME.
  echo "projects/pond"
}

host_ssh_target() {
  local host_id="$1"
  case "${host_id}" in
    jwpc19) echo "jwpc19" ;;
    jwpc12) echo "jwpc12" ;;
    gcweb1) echo "gcweb1" ;;
    *) return 1 ;;
  esac
}

host_install_script() {
  local host_id="$1"
  case "${host_id}" in
    jwpc19) echo "deploy/jwpc19/install-user-units.sh" ;;
    jwpc12) echo "deploy/jwpc12/install-user-units.sh" ;;
    gcweb1) echo "deploy/gcweb1/install-user-units.sh" ;;
    *) return 1 ;;
  esac
}

host_remove_script() {
  local host_id="$1"
  case "${host_id}" in
    jwpc19) echo "deploy/jwpc19/remove-old-units.sh" ;;
    *) echo "" ;;
  esac
}

host_expected_units() {
  local host_id="$1"
  case "${host_id}" in
    jwpc19) echo "pond-dev-sync.service pond-dev-sync.timer" ;;
    jwpc12) echo "pond-scrape.timer pond-weather.timer pond-submit-ingest.service" ;;
    gcweb1) echo "pond-pondupdate-api.service pond-apitest.timer pond-user-chart.timer" ;;
    *) return 1 ;;
  esac
}

host_deprecated_units() {
  local host_id="$1"
  case "${host_id}" in
    jwpc19) echo "pond-rsync-data.service pond-rsync-data.timer" ;;
    gcweb1) echo "pond-submit-edge.service pond-submit-forward.service pond-submit-forward.timer" ;;
    *) echo "" ;;
  esac
}
