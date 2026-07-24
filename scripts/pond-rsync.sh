#!/bin/bash

# fail fast on error, unset variable, or pipe failure
set -euo pipefail
shopt -s nullglob

echo "$(date) start rsync"
cd ~/projects/pond

echo "rsync from $(hostname) to gcweb"

# No longer needed since we now write directly to www-root/ instead of output/
# cp -f ./output/booking-plot-*.png ./www-root/

SRC_DIR="./www-root"
DEST_DIR="gcweb1:projects/pond/www-root/"
RSYNC_OPTS=(-av --itemize-changes)
GENERATED_PATTERNS=(
	"bookings.html"
	"bookings-meta.json"
	"booking-plot-*.png"
)

GENERATED_FILES=()
for pattern in "${GENERATED_PATTERNS[@]}"; do
	for file in "${SRC_DIR}/${pattern}"; do
		if [[ -f "${file}" ]]; then
			GENERATED_FILES+=("${file}")
		fi
	done
done

if [[ ${#GENERATED_FILES[@]} -eq 0 ]]; then
	echo "Error: no generated files found to publish from ${SRC_DIR}" >&2
	exit 1
fi

echo "$(date) preview files to transfer to gcweb1"
rsync "${RSYNC_OPTS[@]}" --dry-run "${GENERATED_FILES[@]}" "$DEST_DIR"

echo "$(date) start rsync to gcweb1"
rsync "${RSYNC_OPTS[@]}" "${GENERATED_FILES[@]}" "$DEST_DIR"

echo "$(date) end pond rsync"


