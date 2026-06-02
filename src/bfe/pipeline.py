from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .citygml.extract import run_extract
from .config import PipelineConfig
from .detect.infer import run_detect
from .logging import get_logger
from .mapillary.fetch import run_fetch
from .merge.report import run_merge

logger = get_logger(__name__)


def resolve_run_dir(cfg: PipelineConfig) -> Path:
    import os
    run_id = (
        cfg.outputs.run_id
        or os.environ.get("BFE_RUN_ID")
        or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    run_dir = cfg.outputs.root / cfg.project / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_pipeline(cfg: PipelineConfig) -> Path:
    run_dir = resolve_run_dir(cfg)
    logger.info("Run directory: %s", run_dir)

    manifest: dict[str, Any] = {
        "package_version": __version__,
        "project": cfg.project,
        "config_snapshot": json.loads(cfg.model_dump_json()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages": {},
    }
    manifest_path = run_dir / "manifest.json"

    def _time_stage(name: str, fn: Callable[[], Path], **extra: Any) -> Path:
        t0 = time.monotonic()
        result = fn()
        manifest["stages"][name] = {
            "duration_s": round(time.monotonic() - t0, 2),
            "output": str(result),
            **extra,
        }
        _write_manifest(manifest_path, manifest)
        return result

    if cfg.footprint.kind == "citygml":
        _time_stage("extract", lambda: run_extract(cfg, run_dir / "stage0_extract"))

    _time_stage("fetch", lambda: run_fetch(cfg, run_dir / "stage1_fetch"))
    _time_stage(
        "detect",
        lambda: run_detect(cfg, run_dir / "stage1_fetch", run_dir / "stage2_detect"),
    )
    geojson_path = _time_stage(
        "merge",
        lambda: run_merge(cfg, run_dir / "stage2_detect", run_dir / "stage3_merge"),
    )

    # Stages 4 and 5 require a running, populated 3DCityDB instance, which is
    # set up outside this process by the orchestrator (scripts/run_pipeline.sh).
    # `bfe pipeline` therefore stops at stage 3; the wrapper calls
    # `bfe enrich` and `bfe visualize` once the citydb is ready.

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_manifest(manifest_path, manifest)

    logger.info("Pipeline complete: %s", geojson_path)
    return geojson_path


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
