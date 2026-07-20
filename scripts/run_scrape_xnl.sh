#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/output"
WWW_ROOT_DIR="${REPO_ROOT}/www-root"
BOOKINGS_CSV="${OUTPUT_DIR}/bookings.csv"
BOOKINGS_SRC="${OUTPUT_DIR}/bookings.html"
BOOKINGS_DST="${WWW_ROOT_DIR}/bookings.html"
LOCK_FILE="${REPO_ROOT}/output/scrape_xnl.lock"
BROWSER_SESSION_DIR="${REPO_ROOT}/browser_session"
RSYNC_SCRIPT="${SCRIPT_DIR}/pond-rsync.sh"
PLOT_SCRIPT_MODULE="pond/booking-plot.py"
REPORT_SCRIPT_MODULE="pond/booking-report.py"
VENV_ACTIVATE="/home/jeremy/projects/heating/dev/ve312heat/bin/activate"
PYTHON_BIN="${PYTHON_BIN:-python}"
HEADLESS_FLAG=""
RUN_RSYNC=0
RUN_PLOT=0
RUN_SCRAPE=0
RUN_FILTERS=0
RUN_WEATHER_DEBUG=0
WEATHER_DEBUG_LOG=""
CRON_MODE=0
SCRAPE_ARGS=()
USER_DATA_DIR="${BROWSER_SESSION_DIR}"

usage() {
  cat <<'EOF'
Usage: run_scrape_xnl.sh [--headless|--no-headless] [--scrape] [--plot] [--rsync] [--cron] [scrape_xnl options]

Options:
  --headless     Run browser in headless mode.
  --no-headless  Force browser to run with UI.
  --scrape       Run pond.scrape_xnl. If omitted, scraping is skipped.
  --plot         Generate booking plots for Men's, Mixed, Ladies, and Lido.
  --filters      Enable filter controls in generated bookings report HTML.
  --weather-debug Enable verbose weather debug logs in booking-report.py.
  --weather-debug-log PATH  Write weather debug logs to PATH.
  --rsync        Run scripts/pond-rsync.sh.
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
    --scrape)
      RUN_SCRAPE=1
      ;;
    --plot)
      RUN_PLOT=1
      ;;
    --filters)
      RUN_FILTERS=1
      ;;
    --weather-debug)
      RUN_WEATHER_DEBUG=1
      ;;
    --weather-debug-log)
      shift
      if (($# == 0)); then
        echo "Error: --weather-debug-log requires a value." >&2
        exit 1
      fi
      WEATHER_DEBUG_LOG="$1"
      ;;
    --weather-debug-log=*)
      WEATHER_DEBUG_LOG="${1#*=}"
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

run_python() {
  printf "Python command: "
  printf "%q " "${PYTHON_BIN}" "$@"
  echo
  "${PYTHON_BIN}" "$@"
}

mkdir -p "${OUTPUT_DIR}" "${WWW_ROOT_DIR}"

cd "${REPO_ROOT}"
if [[ ${RUN_SCRAPE} -eq 1 ]]; then
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

  SCRAPE_CMD_ARGS=( -m pond.scrape_xnl --output-dir "${OUTPUT_DIR}" )
  if [[ -n "${HEADLESS_FLAG}" ]]; then
    SCRAPE_CMD_ARGS+=( "${HEADLESS_FLAG}" )
  fi
  SCRAPE_CMD_ARGS+=( "${SCRAPE_ARGS[@]}" )
  run_python "${SCRAPE_CMD_ARGS[@]}"
else
  echo "Skipping scrape (use --scrape to enable)."
fi

if [[ -f "${BOOKINGS_CSV}" ]]; then
  REPORT_CMD_ARGS=( "${REPORT_SCRIPT_MODULE}" --html-output "${BOOKINGS_SRC}" )
  if [[ ${RUN_FILTERS} -eq 1 ]]; then
    REPORT_CMD_ARGS+=( --filters )
  fi
  if [[ ${RUN_WEATHER_DEBUG} -eq 1 ]]; then
    REPORT_CMD_ARGS+=( --weather-debug )
    if [[ -n "${WEATHER_DEBUG_LOG}" ]]; then
      REPORT_CMD_ARGS+=( --weather-debug-log "${WEATHER_DEBUG_LOG}" )
    fi
  fi
  run_python "${REPORT_CMD_ARGS[@]}"
  cp "${BOOKINGS_SRC}" "${BOOKINGS_DST}"
  echo "Copied ${BOOKINGS_SRC} -> ${BOOKINGS_DST}"
elif [[ ${RUN_SCRAPE} -eq 1 ]]; then
  echo "Error: bookings CSV not found at '${BOOKINGS_CSV}'." >&2
  exit 1
else
  echo "Skipping bookings report (no CSV found at '${BOOKINGS_CSV}')."
fi

if [[ ${RUN_PLOT} -eq 1 ]]; then
  run_python "${PLOT_SCRIPT_MODULE}" --venue "Men's" --prevday --separate-axes --prevday --nextday --per-slot-from -3
  run_python "${PLOT_SCRIPT_MODULE}" --venue "Mixed" --prevday --separate-axes --prevday --nextday --per-slot-from -3
  run_python "${PLOT_SCRIPT_MODULE}" --venue "Ladies" --prevday --separate-axes --prevday --nextday --per-slot-from -3
  run_python "${PLOT_SCRIPT_MODULE}" --venue "Lido" --prevday --separate-axes --prevday --nextday --per-slot-from -3
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
