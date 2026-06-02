from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd

from ..config import BBox, FootprintSource
from ..logging import get_logger

logger = get_logger(__name__)

WGS84 = "EPSG:4326"


def load_footprints(source: FootprintSource, bbox: Optional[BBox] = None) -> gpd.GeoDataFrame:
    if source.kind in ("file", "citygml"):
        gdf = _load_file(source.path, crs_override=source.crs)
    elif source.kind == "osm":
        if bbox is None:
            raise ValueError("footprint.kind='osm' requires a bounding box")
        gdf = _load_osm(bbox)
    else:
        raise ValueError(f"unknown footprint source: {source.kind}")

    gdf = _standardize(gdf, id_field=source.id_field, height_field=source.height_field)
    logger.info("Loaded %d building footprints", len(gdf))
    return gdf


def _load_file(path: Optional[Path], crs_override: Optional[str]) -> gpd.GeoDataFrame:
    if path is None:
        raise ValueError("footprint.kind='file' requires footprint.path")
    if not path.exists():
        raise FileNotFoundError(f"Footprint file not found: {path}")

    logger.info("Reading footprints from %s", path)
    gdf = gpd.read_file(path)

    if gdf.crs is None:
        if crs_override is None:
            raise ValueError(
                f"Footprint file {path} has no CRS and no 'footprint.crs' override was given"
            )
        logger.warning("Footprint file has no CRS; assuming %s", crs_override)
        gdf = gdf.set_crs(crs_override)
    elif crs_override is not None and str(gdf.crs) != crs_override:
        logger.warning("Overriding declared CRS %s with %s", gdf.crs, crs_override)
        gdf = gdf.set_crs(crs_override, allow_override=True)

    if str(gdf.crs) != WGS84:
        gdf = gdf.to_crs(WGS84)

    return gdf


def _load_osm(bbox: BBox) -> gpd.GeoDataFrame:
    import osmnx as ox

    logger.info("Querying OpenStreetMap buildings for bbox %s", bbox.as_string())

    # osmnx changed its `features_from_bbox` signature between 1.9 and 2.0:
    #   - 1.9.x: features_from_bbox(north, south, east, west, tags)
    #   - >=2.0: features_from_bbox(bbox=(left, bottom, right, top), tags=...)
    # Detect at runtime so the same code works against both pins.
    ox_version = tuple(int(p) for p in ox.__version__.split(".")[:2] if p.isdigit())
    tags = {"building": True}
    if ox_version >= (2, 0):
        polygon_gdf = ox.features_from_bbox(
            bbox=(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat),
            tags=tags,
        )
    else:
        polygon_gdf = ox.features_from_bbox(
            north=bbox.max_lat,
            south=bbox.min_lat,
            east=bbox.max_lon,
            west=bbox.min_lon,
            tags=tags,
        )

    polygon_gdf = polygon_gdf[polygon_gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    if polygon_gdf.crs is None:
        polygon_gdf = polygon_gdf.set_crs(WGS84)
    else:
        polygon_gdf = polygon_gdf.to_crs(WGS84)
    return polygon_gdf.reset_index()


def _standardize(
    gdf: gpd.GeoDataFrame,
    id_field: str,
    height_field: Optional[str],
) -> gpd.GeoDataFrame:
    out = gdf.copy()

    if id_field in out.columns:
        out["building_id"] = out[id_field].astype(str)
    elif "osmid" in out.columns:
        out["building_id"] = out["osmid"].astype(str)
    else:
        out["building_id"] = [f"bldg_{i}" for i in range(len(out))]

    if height_field and height_field in out.columns:
        out["height_storeys"] = pd.to_numeric(out[height_field], errors="coerce")
    else:
        out["height_storeys"] = float("nan")

    return out
