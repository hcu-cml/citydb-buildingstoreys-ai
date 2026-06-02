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

    aggregated = _aggregate_per_building(predictions)

    keep_cols = [
        "building_id",
        "windows_detected",
        "floors",
        "height_m",
        "truncated_at_max_floors",
        "skipped_reason",
        "n_images",
    ]
    subset = aggregated[keep_cols].rename(
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
    merged["n_images"] = pd.to_numeric(merged["n_images"], errors="coerce").astype("Int64")

    logger.info(
        "Joined predictions: %d footprints, %d with a floor prediction",
        len(merged),
        int(merged["predicted_floors"].notna().sum()),
    )
    return merged


def _aggregate_per_building(predictions: pd.DataFrame) -> pd.DataFrame:
    scored = predictions[predictions["floors"].notna()].copy()
    skipped = predictions[predictions["floors"].isna()].copy()

    if scored.empty:
        skipped = skipped.drop_duplicates(subset=["building_id"], keep="first")
        skipped["n_images"] = 0
        return skipped

    def _mode_int(series: pd.Series) -> float:
        values = series.dropna().astype(int)
        if values.empty:
            return float("nan")
        modes = values.mode()
        return float(modes.iloc[0]) if not modes.empty else float("nan")

    grouped = (
        scored.groupby("building_id", as_index=False)
        .agg(
            windows_detected=("windows_detected", "sum"),
            floors=("floors", _mode_int),
            height_m=("height_m", "mean"),
            truncated_at_max_floors=("truncated_at_max_floors", "any"),
            n_images=("floors", "size"),
        )
    )
    grouped["skipped_reason"] = pd.NA

    skipped_only = skipped[~skipped["building_id"].isin(grouped["building_id"])].copy()
    skipped_only = skipped_only.drop_duplicates(subset=["building_id"], keep="first")
    skipped_only["n_images"] = 0

    return pd.concat([grouped, skipped_only], ignore_index=True, sort=False)
