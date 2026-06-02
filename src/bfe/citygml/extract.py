"""Stage 0: CityGML -> GeoJSON of building footprints."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ..config import PipelineConfig
from ..logging import get_logger

logger = get_logger(__name__)

SCRIPT_NAME = "extract_citygml2_to_geojson_storeys.py"


def _resolve_script() -> Path:
    """Locate the extractor script across local + Docker layouts."""
    candidates = [
        Path(__file__).resolve().parents[3] / "scripts" / SCRIPT_NAME,
        Path("/app/scripts") / SCRIPT_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def run_extract(cfg: PipelineConfig, stage_dir: Path) -> Path:
    if cfg.footprint.kind != "citygml":
        raise ValueError("run_extract only valid for footprint.kind='citygml'")
    if cfg.footprint.citygml_path is None:
        raise ValueError("footprint.citygml_path is required for stage 0")
    src = cfg.footprint.citygml_path
    if not src.exists():
        raise FileNotFoundError(f"CityGML not found: {src}")
    script = _resolve_script()
    if not script.exists():
        raise FileNotFoundError(f"Extractor script not found: {script}")

    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    out = stage_dir / "footprints.geojson"

    cmd = [sys.executable, str(script), "--input", str(src), "--output", str(out)]
    if cfg.footprint.crs:
        cmd += ["--crs-fallback", cfg.footprint.crs]

    logger.info(
        "Stage 0: extracting %.1f MB CityGML -> %s",
        src.stat().st_size / (1024 * 1024),
        out,
    )
    subprocess.run(cmd, check=True)

    cfg.footprint.path = out

    n_features = _count_features(out)
    logger.info("Stage 0 complete: %d features at %s", n_features, out)
    return out


def _count_features(geojson_path: Path) -> int:
    try:
        with geojson_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return len(data.get("features", []))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not count features in %s: %s", geojson_path, exc)
        return -1
