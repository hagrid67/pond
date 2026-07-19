#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_ACTIVATE="/home/jeremy/projects/heating/dev/ve312heat/bin/activate"
PYTHON_BIN="${PYTHON_BIN:-python}"
LOCK_FILE="${REPO_ROOT}/output/fetch_weather.lock"
LOG_DIR="${REPO_ROOT}/logs"
CRON_MODE=0
METOFFICE_ARGS=()

usage() {
  cat <<'EOF'
Usage: fetch-weather.sh [--cron] [metoffice options]

Runs pond.metoffice with the configured virtual environment.

Options:
  --cron       Emit timestamped start/end markers suitable for cron logs.
  -h, --help   Show this help message.

All other options are passed through to: python -m pond.metoffice

Examples:
  fetch-weather.sh
  fetch-weather.sh --timesteps hourly
  fetch-weather.sh --key "<API_KEY>"
  fetch-weather.sh --cron --timesteps three-hourly
EOF
}

while (($#)); do
  case "$1" in
    --cron)
      CRON_MODE=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      METOFFICE_ARGS+=("$1")
      ;;
  esac
  shift
done

mkdir -p "${REPO_ROOT}/output" "${LOG_DIR}"

if [[ ${CRON_MODE} -eq 1 ]]; then
  echo
  echo "------------------------------------------------------------"
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') fetch-weather.sh start"
  echo "------------------------------------------------------------"
fi

if [[ ! -f "${VENV_ACTIVATE}" ]]; then
  echo "Error: Virtual environment activate script not found at ${VENV_ACTIVATE}" >&2
  exit 1
fi

source "${VENV_ACTIVATE}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    echo "Error: Neither '${PYTHON_BIN}' nor 'python3' was found in PATH." >&2
    exit 1
  fi
fi

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Another fetch-weather run is already in progress; skipping." >&2
  exit 0
fi

cd "${REPO_ROOT}"

printf "Python command: "
printf "%q " "${PYTHON_BIN}" -m pond.metoffice "${METOFFICE_ARGS[@]}"
echo

"${PYTHON_BIN}" -m pond.metoffice "${METOFFICE_ARGS[@]}"

if [[ ${CRON_MODE} -eq 1 ]]; then
  echo "------------------------------------------------------------"
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') fetch-weather.sh end"
  echo "------------------------------------------------------------"
  echo
fi
