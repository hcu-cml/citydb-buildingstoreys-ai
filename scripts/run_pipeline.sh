#!/usr/bin/env bash
# End-to-end runner.
#
# Prerequisites in .env:
#   MAPILLARY_ACCESS_TOKEN   for stages 1+
#   BFE_CITYDB_PASSWORD      for stages 4-5
#
# Usage:
#   ./scripts/run_pipeline.sh heidelberg
#   ./scripts/run_pipeline.sh <area>      # requires configs/<area>.yaml + data/<area>.gml

set -euo pipefail

AREA="${1:?usage: $0 <area>}"
CFG="configs/${AREA}.yaml"

if [[ ! -f .env ]]; then
    echo "missing .env (copy .env.example and set MAPILLARY_ACCESS_TOKEN, BFE_CITYDB_PASSWORD)" >&2
    exit 2
fi
if [[ ! -f "${CFG}" ]]; then
    echo "missing ${CFG}" >&2
    exit 2
fi

# shellcheck disable=SC1091
# Read BFE_* vars from .env without `source`-ing it, so values containing '|' or
# other shell-special characters (e.g. Mapillary tokens) don't get split.
_read_env() {
    grep -E "^${1}=" .env 2>/dev/null \
        | tail -n1 \
        | sed -E "s/^${1}=//; s/^[\"']//; s/[\"']$//"
}
BFE_CITYDB_PASSWORD="$(_read_env BFE_CITYDB_PASSWORD)"
BFE_CITYDB_NAME="$(_read_env BFE_CITYDB_NAME)"
: "${BFE_CITYDB_PASSWORD:?BFE_CITYDB_PASSWORD must be set in .env}"
DBNAME="${BFE_CITYDB_NAME:-${AREA}_citydb5}"
NETWORK="$(basename "${PWD}" | tr '[:upper:]' '[:lower:]')_default"

GML_PATH_HOST="$(python3 - <<PY
import yaml, os
with open("${CFG}") as f:
    cfg = yaml.safe_load(f)
p = cfg.get("footprint", {}).get("citygml_path")
if not p:
    print("")
else:
    base = os.path.dirname(os.path.abspath("${CFG}"))
    abs_p = p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    print(os.path.relpath(abs_p, os.path.abspath(".")))
PY
)"
if [[ -z "${GML_PATH_HOST}" ]]; then
    echo "${CFG}: footprint.citygml_path is required" >&2
    exit 2
fi

# Reuse a single run dir across the whole orchestration so stages 4-5 land
# in the same outputs/<area>/<run_id>/ as stages 0-3.
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
echo "    run id: ${RUN_ID}"

echo "=== build pipeline image ==="
docker compose --profile pipeline build pipeline

echo "=== bring up citydb stack ==="
docker compose --profile citydb up -d citydb-postgres nginx-tiles viewer

echo "=== stages 0..3 (extract, fetch, detect, merge) + initial 4-5 ==="
docker compose --profile pipeline run --rm \
    -e BFE_RUN_ID="${RUN_ID}" \
    pipeline pipeline --config "/app/${CFG}"

RUN_HOST="outputs/${AREA}/${RUN_ID}"
[[ -d "${RUN_HOST}" ]] || { echo "missing ${RUN_HOST}" >&2; exit 2; }

echo "=== import CityGML into citydb ==="
docker compose --profile citydb run --rm --entrypoint citydb citydb-tool \
    import citygml \
    -H citydb-postgres -d "${DBNAME}" \
    -u postgres -p "${BFE_CITYDB_PASSWORD}" \
    "/app/${GML_PATH_HOST}"

echo "=== stage 4 (enrich; rerun against populated citydb) ==="
docker compose --profile citydb run --rm \
    -e BFE_RUN_ID="${RUN_ID}" \
    enrich enrich --config "/app/${CFG}"

echo "=== stage 5 (build materialized view + 3D Tiles via pg2b3dm) ==="
docker compose exec -T -e PGPASSWORD="${BFE_CITYDB_PASSWORD}" \
    citydb-postgres psql -U postgres -d "${DBNAME}" \
    < infra/bfe_buildings.sql

TILES_HOST="${RUN_HOST}/stage5_publish/tiles"
mkdir -p "${TILES_HOST}"
docker run --rm --network "${NETWORK}" \
    -v "${PWD}/${TILES_HOST}:/app/output" \
    geodan/pg2b3dm:latest \
    --connection "Host=citydb-postgres;Port=5432;Username=postgres;Password=${BFE_CITYDB_PASSWORD};Database=${DBNAME};CommandTimeOut=0" \
    --table citydb.bfe_buildings \
    --column geom \
    --attributecolumns floors \
    --output /app/output

# visualize writes the 3DWebMC config + style and updates outputs/<area>/current.
docker compose --profile pipeline run --rm \
    -e BFE_RUN_ID="${RUN_ID}" \
    pipeline visualize --config "/app/${CFG}"

cat <<EOF

=== done ===
Run dir:  ${RUN_HOST}
Viewer:   http://localhost:8080/viewer.html
Tiles:    http://localhost:8080/tiles/tileset.json
Browse:   http://localhost:8080/outputs/
EOF
