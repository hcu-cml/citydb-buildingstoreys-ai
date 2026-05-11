from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import PipelineConfig
from .detect.infer import run_detect
from .logging import get_logger
from .mapillary.fetch import run_fetch
from .merge.report import run_merge

logger = get_logger(__name__)


def resolve_run_dir(cfg: PipelineConfig) -> Path:
    run_id = cfg.outputs.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = cfg.outputs.root / cfg.project / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_pipeline(cfg: PipelineConfig) -> Path:
    run_dir = resolve_run_dir(cfg)
    logger.info("Run directory: %s", run_dir)

    manifest: dict[str, object] = {
        "package_version": __version__,
        "project": cfg.project,
        "config_snapshot": json.loads(cfg.model_dump_json()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages": {},
    }
    manifest_path = run_dir / "manifest.json"

    stage1_dir = run_dir / "stage1_fetch"
    stage2_dir = run_dir / "stage2_detect"
    stage3_dir = run_dir / "stage3_merge"

    t0 = time.monotonic()
    metadata_path = run_fetch(cfg, stage1_dir)
    manifest["stages"]["fetch"] = {
        "duration_s": round(time.monotonic() - t0, 2),
        "metadata": str(metadata_path),
    }
    _write_manifest(manifest_path, manifest)

    t1 = time.monotonic()
    predictions_path = run_detect(cfg, stage1_dir, stage2_dir)
    manifest["stages"]["detect"] = {
        "duration_s": round(time.monotonic() - t1, 2),
        "predictions": str(predictions_path),
    }
    _write_manifest(manifest_path, manifest)

    t2 = time.monotonic()
    geojson_path = run_merge(cfg, stage2_dir, stage3_dir)
    manifest["stages"]["merge"] = {
        "duration_s": round(time.monotonic() - t2, 2),
        "geojson": str(geojson_path),
    }
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_manifest(manifest_path, manifest)

    logger.info("Pipeline complete. Final GeoJSON: %s", geojson_path)
    return geojson_path


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
