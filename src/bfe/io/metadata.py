from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

MAPILLARY_METADATA_COLUMNS: tuple[str, ...] = (
    "building_id",
    "image_filename",
    "image_id",
    "building_lat",
    "building_lon",
    "image_lat",
    "image_lon",
    "distance_m",
    "bearing_deg",
    "bearing_diff_deg",
    "captured_at",
    "height_storeys",
)

PREDICTIONS_COLUMNS: tuple[str, ...] = (
    "building_id",
    "image_filename",
    "windows_detected",
    "floors",
    "floors_kmeans",
    "floors_gmm",
    "floors_dbscan",
    "height_m",
    "truncated_at_max_floors",
    "skipped_reason",
)


def write_parquet(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    columns: tuple[str, ...],
) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(list(rows))
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df = df[list(columns)]
    df.to_parquet(path, index=False)
    return len(df)


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
