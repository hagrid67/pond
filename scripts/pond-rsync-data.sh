#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Warning: pond-rsync-data.sh is deprecated; use pond-dev-sync.sh" >&2
exec "${SCRIPT_DIR}/pond-dev-sync.sh" "$@"


