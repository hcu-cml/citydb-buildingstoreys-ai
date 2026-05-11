#!/usr/bin/env bash
# Download the YOLO window-detection weights used in the paper.
#
# This helper only works with a DIRECT file URL (Zenodo asset, GitHub
# release asset, Hugging Face file URL, etc.). Google Drive folder links
# cannot be fetched with curl; download manually from the Drive folder
# linked in the README if that is the only source available.
#
# Optionally set WEIGHTS_SHA256 to the expected checksum to verify the
# download.
#
# Usage:
#   WEIGHTS_URL=https://example.org/best.pt ./scripts/download_weights.sh

set -euo pipefail

WEIGHTS_URL="${WEIGHTS_URL:-}"
WEIGHTS_SHA256="${WEIGHTS_SHA256:-}"
DEST="${DEST:-models/best.pt}"

if [[ -z "$WEIGHTS_URL" ]]; then
    echo "WEIGHTS_URL is not set. Export it or pass it inline:" >&2
    echo "  WEIGHTS_URL=https://example.org/best.pt $0" >&2
    exit 1
fi

mkdir -p "$(dirname "$DEST")"

if [[ -f "$DEST" ]]; then
    echo "Weights already present at $DEST; delete the file to re-download." >&2
    exit 0
fi

echo "Downloading YOLO weights from $WEIGHTS_URL to $DEST ..."
curl -fL --retry 3 --retry-delay 2 -o "$DEST" "$WEIGHTS_URL"

if [[ -n "$WEIGHTS_SHA256" ]]; then
    echo "Verifying SHA-256 ..."
    actual="$(sha256sum "$DEST" | awk '{print $1}')"
    if [[ "$actual" != "$WEIGHTS_SHA256" ]]; then
        echo "Checksum mismatch! expected=$WEIGHTS_SHA256 actual=$actual" >&2
        rm -f "$DEST"
        exit 1
    fi
    echo "Checksum OK."
fi

echo "Done: $DEST"
