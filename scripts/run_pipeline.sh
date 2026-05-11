#!/usr/bin/env bash
# End-to-end pipeline runner inside Docker.
#
# Prerequisites:
#   - A .env file at the repo root with MAPILLARY_ACCESS_TOKEN set.
#   - A footprint file under ./data/ matching the config.
#   - YOLO weights under ./models/best.pt (or as configured).
#
# Usage:
#   ./scripts/run_pipeline.sh configs/heidelberg.yaml

set -euo pipefail

CONFIG="${1:-configs/heidelberg.yaml}"

if [[ ! -f .env ]]; then
    echo "No .env file found; copy .env.example to .env and fill in MAPILLARY_ACCESS_TOKEN." >&2
    exit 1
fi

docker compose build
docker compose run --rm pipeline bfe pipeline --config "/app/${CONFIG}"
