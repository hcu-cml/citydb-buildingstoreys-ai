from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class FootprintSource(BaseModel):
    kind: Literal["file", "osm"] = "file"
    path: Optional[Path] = None
    crs: Optional[str] = None
    id_field: str = "id"
    height_field: Optional[str] = "storeysAboveGround"


class BBox(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def as_string(self) -> str:
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"


class MapillaryConfig(BaseModel):
    bbox: BBox
    grid_divisions: int = 4
    search_radius_m: float = 150.0
    bearing_tolerance_deg: float = 90.0
    max_images_per_building: int = 1
    request_limit: int = 2000
    max_pages_per_cell: int = 20
    request_timeout_s: float = 30.0
    per_cell_sleep_s: float = 2.0
    per_page_sleep_s: float = 1.0


class DetectorConfig(BaseModel):
    weights: Path
    confidence_threshold: float = 0.15
    iou_threshold: float = 0.12
    device: Literal["auto", "cpu", "cuda"] = "auto"
    target_class: str = "window"


class FloorEstimatorConfig(BaseModel):
    min_windows: int = 8
    max_floors: int = 5
    avg_floor_height_m: float = 2.5


class OutputsConfig(BaseModel):
    root: Path = Path("outputs")
    run_id: Optional[str] = None


class PipelineConfig(BaseModel):
    project: str = "heidelberg"
    footprint: FootprintSource
    mapillary: MapillaryConfig
    detector: DetectorConfig
    floor_estimator: FloorEstimatorConfig = FloorEstimatorConfig()
    outputs: OutputsConfig = OutputsConfig()

    @field_validator("project")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not value or any(c.isspace() for c in value):
            raise ValueError("project must be a non-empty slug without whitespace")
        return value


def load_config(path: Path) -> PipelineConfig:
    path = Path(path).resolve()
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    cfg = PipelineConfig.model_validate(raw)
    base = path.parent

    def _resolve(p: Optional[Path]) -> Optional[Path]:
        if p is None:
            return None
        p = Path(p)
        return p if p.is_absolute() else (base / p).resolve()

    if cfg.footprint.path is not None:
        cfg.footprint.path = _resolve(cfg.footprint.path)
    cfg.detector.weights = _resolve(cfg.detector.weights)  # type: ignore[assignment]
    cfg.outputs.root = _resolve(cfg.outputs.root)  # type: ignore[assignment]

    return cfg
