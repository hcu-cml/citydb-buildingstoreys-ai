"""Stage 5: build a 3D Tiles tileset and 3DCityDB Web Map Client config.

The actual tile export uses pg2b3dm against a materialized view that joins
the citydb feature/property tables; this module is responsible for the
viewer-side artifacts (tileset placeholder when tiles are absent, layer
config and styling JSON, and the ``current`` symlink that nginx serves).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import PipelineConfig
from ..logging import get_logger

logger = get_logger(__name__)

_DEFAULT_TILE_EXPORT_ARGS = [
    "export",
    "tiles",
    "--target-srs",
    "EPSG:4978",
    "--tile-format",
    "b3dm",
    "--include-attribute",
    "storeysAboveGround",
    "--feature-id-attribute",
    "objectid",
]


def run_visualize(cfg: PipelineConfig, stage_dir: Path) -> Path:
    if not cfg.visualization.enabled:
        raise ValueError("run_visualize requires visualization.enabled=true")
    if cfg.enrichment.citydb is None:
        raise ValueError("run_visualize requires enrichment.citydb")

    stage_dir = Path(stage_dir)
    tiles_dir = stage_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    tileset = _export_tiles(cfg, tiles_dir)

    _write_viewer_config(cfg, stage_dir)
    _update_current_symlink(cfg, stage_dir)

    report = {
        "started_at": started_at,
        "duration_s": round(time.monotonic() - t0, 2),
        "tiles_dir": str(tiles_dir),
        "tileset": str(tileset),
        "viewer_url": f"http://localhost:{cfg.visualization.viewer_port}",
        "tiles_url": f"http://localhost:{cfg.visualization.nginx_port}/tiles/tileset.json",
    }
    (stage_dir / "visualize_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    logger.info("Stage 5 complete: %s -> %s", tileset, report["viewer_url"])
    return tileset


def _export_tiles(cfg: PipelineConfig, tiles_dir: Path) -> Path:
    tileset = tiles_dir / "tileset.json"
    if tileset.exists() and tileset.stat().st_size > 0:
        logger.info("Reusing existing tileset at %s", tileset)
        return tileset

    citydb_tool = shutil.which("citydb")
    if citydb_tool is None:
        logger.warning("citydb-tool not found in PATH; writing placeholder tileset.json")
        return _write_placeholder_tileset(tiles_dir)

    db = cfg.enrichment.citydb
    assert db is not None
    env = os.environ.copy()
    env.setdefault("PGHOST", db.host)
    env.setdefault("PGPORT", str(db.port))
    env.setdefault("PGDATABASE", db.database)
    env.setdefault("PGUSER", db.user)

    cmd = [citydb_tool, *_DEFAULT_TILE_EXPORT_ARGS]
    cmd += [
        "--connect-string",
        f"jdbc:postgresql://{db.host}:{db.port}/{db.database}",
        "--db-username",
        db.user,
    ]
    if pw := (env.get("BFE_CITYDB_PASSWORD") or env.get("PGPASSWORD")):
        cmd += ["--db-password", pw]
    cmd += ["--output", str(tiles_dir)]
    cmd += list(cfg.visualization.tile_export_args)

    logger.info("Running citydb-tool: %s ...", " ".join(cmd[:8]))
    subprocess.run(cmd, env=env, check=True)

    tileset = tiles_dir / "tileset.json"
    if not tileset.exists():
        logger.warning("citydb-tool finished but tileset.json is missing; writing placeholder")
        return _write_placeholder_tileset(tiles_dir)
    return tileset


def _write_placeholder_tileset(tiles_dir: Path) -> Path:
    tileset = tiles_dir / "tileset.json"
    if tileset.exists():
        return tileset
    placeholder = {
        "asset": {"version": "1.0"},
        "geometricError": 500,
        "root": {
            "boundingVolume": {"region": [0.150, 0.860, 0.155, 0.864, 0, 100]},
            "geometricError": 500,
            "refine": "ADD",
        },
    }
    tileset.write_text(json.dumps(placeholder, indent=2), encoding="utf-8")
    return tileset


def _write_viewer_config(cfg: PipelineConfig, stage_dir: Path) -> None:
    threed = stage_dir / "3dwebmc"
    threed.mkdir(parents=True, exist_ok=True)

    rule = cfg.visualization.styling.color_rule
    by = cfg.visualization.styling.by

    conditions = []
    for k, color in rule.items():
        if k == "default":
            continue
        conditions.append([f"${{{by}}} === {int(k)}", f"color('{color}')"])
    conditions.append(["true", f"color('{rule.get('default', 'gray')}')"])

    style = {"color": {"conditions": conditions}}
    (threed / "style.json").write_text(json.dumps(style, indent=2), encoding="utf-8")

    base_url = {
        "arcgis": (
            "https://services.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        "osm": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "bing": "https://ecn.t0.tiles.virtualearth.net/tiles/a{q}.jpeg",
    }[cfg.visualization.basemap]

    config = {
        "name": cfg.project,
        "layers": [
            {
                "name": f"{cfg.project} buildings",
                "url": "/tiles/tileset.json",
                "type": "3DTiles",
                "active": True,
                "styleUrl": "/3dwebmc/style.json",
                "attribute": by,
            }
        ],
        "baseLayer": {"url": base_url, "type": "tms"},
    }
    (threed / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _update_current_symlink(cfg: PipelineConfig, stage_dir: Path) -> None:
    project_dir = cfg.outputs.root / cfg.project
    current = project_dir / "current"
    target = stage_dir
    try:
        if current.is_symlink() or current.exists():
            current.unlink()
        current.symlink_to(
            os.path.relpath(target, project_dir),
            target_is_directory=True,
        )
        logger.info("Updated %s -> %s", current, target)
    except OSError as exc:
        logger.warning("Could not update %s symlink: %s", current, exc)
