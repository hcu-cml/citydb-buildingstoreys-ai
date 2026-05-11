from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import PipelineConfig
from ..io.geojson import load_footprints
from ..io.metadata import read_parquet
from ..logging import get_logger

logger = get_logger(__name__)


def join_predictions(cfg: PipelineConfig, predictions_path: Path) -> gpd.GeoDataFrame:
    buildings = load_footprints(cfg.footprint, bbox=cfg.mapillary.bbox)
    predictions = read_parquet(predictions_path)

    predictions = predictions.drop_duplicates(subset=["building_id"], keep="first")

    keep_cols = [
        "building_id",
        "windows_detected",
        "floors",
        "height_m",
        "truncated_at_max_floors",
        "skipped_reason",
    ]
    subset = predictions[keep_cols].rename(
        columns={"floors": "predicted_floors", "height_m": "predicted_height_m"}
    )

    merged = buildings.merge(subset, on="building_id", how="left")
    merged["windows_detected"] = pd.to_numeric(
        merged["windows_detected"], errors="coerce"
    ).astype("Int64")
    merged["predicted_floors"] = pd.to_numeric(merged["predicted_floors"], errors="coerce")
    merged["predicted_height_m"] = pd.to_numeric(merged["predicted_height_m"], errors="coerce")
    merged["truncated_at_max_floors"] = (
        merged["truncated_at_max_floors"].fillna(False).astype(bool)
    )

    logger.info(
        "Joined predictions: %d footprints, %d with a floor prediction",
        len(merged),
        int(merged["predicted_floors"].notna().sum()),
    )
    return merged
