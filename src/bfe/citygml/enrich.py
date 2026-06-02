"""Stage 4: write predicted floor counts into 3DCityDB."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import PipelineConfig
from ..logging import get_logger

logger = get_logger(__name__)

SCRIPT_NAME = "add_geojson_storeys_to_citygml2.py"


def _resolve_script() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / "scripts" / SCRIPT_NAME,
        Path("/app/scripts") / SCRIPT_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]
_RESULTS_RE = re.compile(r"STORE_RESULTS\s+(\{.*\})")


def run_enrich(cfg: PipelineConfig, merge_dir: Path, stage_dir: Path) -> Path:
    if not cfg.enrichment.enabled:
        raise ValueError("run_enrich requires enrichment.enabled=true")
    if cfg.enrichment.citydb is None:
        raise ValueError("run_enrich requires enrichment.citydb")
    script = _resolve_script()
    if not script.exists():
        raise FileNotFoundError(f"Enrichment script not found: {script}")

    merge_dir = Path(merge_dir)
    stage_dir = Path(stage_dir)
    geojson = merge_dir / "buildings_with_predictions.geojson"
    if not geojson.exists():
        raise FileNotFoundError(f"Stage 3 output not found: {geojson}")

    stage_dir.mkdir(parents=True, exist_ok=True)

    db = cfg.enrichment.citydb
    env = os.environ.copy()
    env["PGHOST"] = db.host
    env["PGPORT"] = str(db.port)
    env["PGDATABASE"] = db.database
    env["PGUSER"] = db.user
    if "BFE_CITYDB_PASSWORD" not in env and "PGPASSWORD" not in env:
        raise RuntimeError("BFE_CITYDB_PASSWORD or PGPASSWORD must be set")

    log_file = stage_dir / "enrich.log"
    cmd = [sys.executable, str(script), "--input", str(geojson), "--log", str(log_file)]
    logger.info("Stage 4: enriching citydb '%s' from %s", db.database, geojson)

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    duration_s = round(time.monotonic() - t0, 2)

    counts = _parse_results(proc.stdout) or _parse_results(proc.stderr) or {}
    if log_file.exists():
        try:
            counts = _parse_results(log_file.read_text(encoding="utf-8")) or counts
        except OSError:
            pass

    report = {
        "started_at": started_at,
        "duration_s": duration_s,
        "geojson": str(geojson),
        "database": db.database,
        "host": db.host,
        "port": db.port,
        "log": str(log_file),
        "n_records": counts.get("n_records"),
        "n_updates": counts.get("n_updates"),
        "n_inserts": counts.get("n_inserts"),
    }
    out = stage_dir / "enrich_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info(
        "Stage 4 complete: %s records (updates=%s inserts=%s)",
        counts.get("n_records"),
        counts.get("n_updates"),
        counts.get("n_inserts"),
    )
    return out


def _parse_results(text: str) -> dict | None:
    if not text:
        return None
    m = _RESULTS_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
