#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNNER_SCRIPT="${SCRIPT_DIR}/run_scrape_xnl.sh"
SOURCE_HOST="${POND_SYNC_SOURCE_HOST:-jwpc12}"
PROD_HOST="${POND_SYNC_PROD_HOST:-gcweb1}"
REQUIRED_HOSTNAME="jwpc19"

CURRENT_HOSTNAME="$(hostname -s)"
if [[ "${CURRENT_HOSTNAME}" != "${REQUIRED_HOSTNAME}" ]]; then
  echo "Error: this script must be run on ${REQUIRED_HOSTNAME}, current host is ${CURRENT_HOSTNAME}" >&2
  exit 1
fi

echo "$(date) start pond dev sync"
cd "${REPO_ROOT}"

echo "$(date) rsync external data from ${SOURCE_HOST} to $(hostname)"
rsync -av "${SOURCE_HOST}:projects/pond/data/" "${REPO_ROOT}/data/"
rsync -av "${SOURCE_HOST}:projects/pond/metoffice-data/" "${REPO_ROOT}/metoffice-data/"

echo "$(date) rsync user updates from ${PROD_HOST} to $(hostname)"
rsync -av "${PROD_HOST}:projects/pond/user-updates/" "${REPO_ROOT}/user-updates/"

if [[ ! -x "${RUNNER_SCRIPT}" ]]; then
  echo "Error: script not executable: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "$(date) regenerate bookings report and booking plots"
"${RUNNER_SCRIPT}" --plot --filters

echo "$(date) end pond dev sync"
