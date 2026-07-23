#!/bin/bash

# fail fast on error, unset variable, or pipe failure
set -euo pipefail

echo "$(date) start rsync"
cd ~/projects/pond

echo "rsync from $(hostname) to gcweb"

cp -f ./output/booking-plot-*.png ./www-root/

SRC_DIR="./www-root/"
DEST_DIR="gcweb1:projects/heating/dev/www-root/"
RSYNC_OPTS=(-av --itemize-changes)

echo "$(date) preview files to transfer to gcweb1"
rsync "${RSYNC_OPTS[@]}" --dry-run "$SRC_DIR" "$DEST_DIR"

echo "$(date) start rsync to gcweb1"
rsync "${RSYNC_OPTS[@]}" "$SRC_DIR" "$DEST_DIR"

echo "$(date) end pond rsync"


