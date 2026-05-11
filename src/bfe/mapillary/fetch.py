from __future__ import annotations

import math
import time
from pathlib import Path

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import MapillaryConfig, PipelineConfig
from ..io.geojson import load_footprints
from ..io.metadata import MAPILLARY_METADATA_COLUMNS, write_parquet
from ..logging import get_logger
from .client import MapillaryClient
from .grid import split_bbox
from .matching import match_images_to_building

logger = get_logger(__name__)


def run_fetch(cfg: PipelineConfig, stage_dir: Path) -> Path:
    stage_dir = Path(stage_dir)
    images_dir = stage_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    buildings = load_footprints(cfg.footprint, bbox=cfg.mapillary.bbox)
    all_images = _fetch_all_images(cfg.mapillary)
    if not all_images:
        logger.warning("No Mapillary images returned for bbox %s", cfg.mapillary.bbox.as_string())

    session = requests.Session()
    metadata: list[dict] = []
    matched_buildings = 0
    downloaded = 0

    for idx, row in enumerate(buildings.itertuples(index=False)):
        centroid = getattr(row, "geometry").centroid
        building_lat, building_lon = float(centroid.y), float(centroid.x)
        building_id = str(getattr(row, "building_id"))
        height_storeys = getattr(row, "height_storeys", None)

        if idx % 100 == 0:
            logger.info(
                "Matching progress: %d/%d buildings (downloaded: %d)",
                idx, len(buildings), downloaded,
            )

        matches = match_images_to_building(
            building_lat=building_lat,
            building_lon=building_lon,
            images=all_images,
            search_radius_m=cfg.mapillary.search_radius_m,
            bearing_tolerance_deg=cfg.mapillary.bearing_tolerance_deg,
            max_images=cfg.mapillary.max_images_per_building,
        )
        if not matches:
            continue

        matched_buildings += 1
        for img_idx, match in enumerate(matches):
            if not match.thumb_url:
                continue

            filename = f"{building_id}_{img_idx:02d}.jpg"
            dest = images_dir / filename
            if not _download_image(session, match.thumb_url, dest):
                continue

            metadata.append({
                "building_id": building_id,
                "image_filename": filename,
                "image_id": match.image_id,
                "building_lat": building_lat,
                "building_lon": building_lon,
                "image_lat": match.lat,
                "image_lon": match.lon,
                "distance_m": round(match.distance_m, 2),
                "bearing_deg": round(match.bearing, 2),
                "bearing_diff_deg": round(match.bearing_diff_deg, 2),
                "captured_at": match.captured_at,
                "height_storeys": _opt_float(height_storeys),
            })
            downloaded += 1

    metadata_path = stage_dir / "mapillary_metadata.parquet"
    n_rows = write_parquet(metadata_path, metadata, MAPILLARY_METADATA_COLUMNS)

    logger.info(
        "Stage 1 complete: %d buildings matched, %d images downloaded, %d rows at %s",
        matched_buildings, downloaded, n_rows, metadata_path,
    )
    return metadata_path


def _fetch_all_images(cfg: MapillaryConfig) -> list[dict]:
    cells = split_bbox(cfg.bbox, cfg.grid_divisions)
    logger.info("Fetching Mapillary images for %d cells", len(cells))

    client = MapillaryClient(
        limit=cfg.request_limit,
        timeout_s=cfg.request_timeout_s,
        max_pages_per_cell=cfg.max_pages_per_cell,
        per_page_sleep_s=cfg.per_page_sleep_s,
    )

    seen_ids: set[str] = set()
    aggregated: list[dict] = []

    for idx, cell in enumerate(cells, start=1):
        logger.info("Cell %d/%d: %s", idx, len(cells), cell.as_string())
        try:
            records = client.fetch_bbox(cell)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cell %d failed: %s", idx, exc)
            continue

        new_records = [r for r in records if str(r.get("id")) not in seen_ids]
        for r in new_records:
            seen_ids.add(str(r.get("id")))
        aggregated.extend(new_records)
        logger.info(
            "Cell %d: %d images (%d new), total unique: %d",
            idx, len(records), len(new_records), len(aggregated),
        )

        if cfg.per_cell_sleep_s > 0 and idx < len(cells):
            time.sleep(cfg.per_cell_sleep_s)

    return aggregated


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
)
def _download_image(session: requests.Session, url: str, dest: Path) -> bool:
    response = session.get(url, timeout=15, stream=True)
    if response.status_code != 200:
        return False
    with dest.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)
    return True


def _opt_float(value: object) -> float | None:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None
