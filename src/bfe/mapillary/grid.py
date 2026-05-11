from __future__ import annotations

from ..config import BBox


def split_bbox(bbox: BBox, divisions: int) -> list[BBox]:
    if divisions < 1:
        raise ValueError("divisions must be >= 1")

    lon_step = (bbox.max_lon - bbox.min_lon) / divisions
    lat_step = (bbox.max_lat - bbox.min_lat) / divisions

    cells: list[BBox] = []
    for i in range(divisions):
        for j in range(divisions):
            cells.append(
                BBox(
                    min_lon=bbox.min_lon + j * lon_step,
                    min_lat=bbox.min_lat + i * lat_step,
                    max_lon=bbox.min_lon + (j + 1) * lon_step,
                    max_lat=bbox.min_lat + (i + 1) * lat_step,
                )
            )
    return cells
