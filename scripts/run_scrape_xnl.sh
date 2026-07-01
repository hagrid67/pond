#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/output"
WWW_ROOT_DIR="${REPO_ROOT}/www-root"
BOOKINGS_SRC="${OUTPUT_DIR}/bookings.html"
BOOKINGS_DST="${WWW_ROOT_DIR}/bookings.html"
LOCK_FILE="${REPO_ROOT}/output/scrape_xnl.lock"
BROWSER_SESSION_DIR="${REPO_ROOT}/browser_session"
RSYNC_SCRIPT="${SCRIPT_DIR}/pond-rsync.sh"
PLOT_SCRIPT_MODULE="pond/booking-plot.py"
VENV_ACTIVATE="/home/jeremy/projects/heating/dev/ve312heat/bin/activate"
PYTHON_BIN="${PYTHON_BIN:-python}"
HEADLESS_FLAG=""
RUN_RSYNC=0
RUN_PLOT=0
CRON_MODE=0
SCRAPE_ARGS=()
USER_DATA_DIR="${BROWSER_SESSION_DIR}"

usage() {
  cat <<'EOF'
Usage: run_scrape_xnl.sh [--headless|--no-headless] [--plot] [--rsync] [--cron] [scrape_xnl options]

Options:
  --headless     Run browser in headless mode.
  --no-headless  Force browser to run with UI.
  --plot         Generate booking plots for Men's, Mixed, and Ladies after scraping.
  --rsync        Run scripts/pond-rsync.sh after successful scrape.
  --cron         Emit extra timestamped separators and blank lines for cron logs.
  -h, --help     Show this help message.

All other options are passed through to pond.scrape_xnl.
EOF
}

while (($#)); do
  case "$1" in
    --headless)
      HEADLESS_FLAG="--headless"
      ;;
    --no-headless)
      HEADLESS_FLAG=""
      ;;
    --rsync)
      RUN_RSYNC=1
      ;;
    --plot)
      RUN_PLOT=1
      ;;
    --cron)
      CRON_MODE=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --user-data-dir)
      SCRAPE_ARGS+=("$1")
      shift
      if (($# == 0)); then
        echo "Error: --user-data-dir requires a value." >&2
        exit 1
      fi
      USER_DATA_DIR="$1"
      SCRAPE_ARGS+=("$1")
      ;;
    --user-data-dir=*)
      USER_DATA_DIR="${1#*=}"
      SCRAPE_ARGS+=("$1")
      ;;
    *)
      SCRAPE_ARGS+=("$1")
      ;;
  esac
  shift
done

if [[ ${CRON_MODE} -eq 1 ]]; then
  echo
  echo
  echo "------------------------------------------------------------"
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') run_scrape_xnl.sh start"
  echo "------------------------------------------------------------"
  echo
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

mkdir -p "${OUTPUT_DIR}" "${WWW_ROOT_DIR}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Another scrape_xnl run is already in progress; skipping." >&2
  exit 0
fi

if [[ -e "${USER_DATA_DIR}/SingletonLock" ]]; then
  if pgrep -fa "(chromium|chrome).*(--user-data-dir=${USER_DATA_DIR}|${USER_DATA_DIR})" >/dev/null 2>&1; then
    echo "Browser profile is already in use (${USER_DATA_DIR}); skipping." >&2
    exit 0
  fi
  rm -f "${USER_DATA_DIR}/SingletonLock" "${USER_DATA_DIR}/SingletonSocket" "${USER_DATA_DIR}/SingletonCookie"
fi

cd "${REPO_ROOT}"
"${PYTHON_BIN}" -m pond.scrape_xnl --output-dir "${OUTPUT_DIR}" ${HEADLESS_FLAG:+"${HEADLESS_FLAG}"} "${SCRAPE_ARGS[@]}"

if [[ ! -f "${BOOKINGS_SRC}" ]]; then
  echo "Error: Scrape finished but '${BOOKINGS_SRC}' was not created." >&2
  exit 1
fi

cp "${BOOKINGS_SRC}" "${BOOKINGS_DST}"
echo "Copied ${BOOKINGS_SRC} -> ${BOOKINGS_DST}"

if [[ ${RUN_PLOT} -eq 1 ]]; then
  "${PYTHON_BIN}" "${PLOT_SCRIPT_MODULE}" --venue "Men's"
  "${PYTHON_BIN}" "${PLOT_SCRIPT_MODULE}" --venue "Mixed"
  "${PYTHON_BIN}" "${PLOT_SCRIPT_MODULE}" --venue "Ladies"
fi

if [[ ${RUN_RSYNC} -eq 1 ]]; then
  if [[ ! -x "${RSYNC_SCRIPT}" ]]; then
    echo "Error: rsync script not executable: ${RSYNC_SCRIPT}" >&2
    exit 1
  fi
  "${RSYNC_SCRIPT}"
fi

if [[ ${CRON_MODE} -eq 1 ]]; then
  echo
  echo "------------------------------------------------------------"
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') run_scrape_xnl.sh end"
  echo "------------------------------------------------------------"
  echo
  echo
fi
