#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/output"
WWW_ROOT_DIR="${REPO_ROOT}/www-root"
BOOKINGS_SRC="${OUTPUT_DIR}/bookings.html"
BOOKINGS_DST="${WWW_ROOT_DIR}/bookings.html"
VENV_ACTIVATE="/home/jeremy/projects/heating/dev/ve312heat/bin/activate"
PYTHON_BIN="${PYTHON_BIN:-python}"

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

cd "${REPO_ROOT}"
"${PYTHON_BIN}" -m pond.scrape_xnl --output-dir "${OUTPUT_DIR}" "$@"

if [[ ! -f "${BOOKINGS_SRC}" ]]; then
  echo "Error: Scrape finished but '${BOOKINGS_SRC}' was not created." >&2
  exit 1
fi

cp "${BOOKINGS_SRC}" "${BOOKINGS_DST}"
echo "Copied ${BOOKINGS_SRC} -> ${BOOKINGS_DST}"
