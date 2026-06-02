from __future__ import annotations

from pathlib import Path

import cv2

from ..config import PipelineConfig
from ..io.metadata import PREDICTIONS_COLUMNS, read_parquet, write_parquet
from ..logging import get_logger
from .floors import estimate_floors
from .model import load_yolo_model, resolve_device
from .windows import assert_target_class_supported, detect_windows

logger = get_logger(__name__)


def run_detect(cfg: PipelineConfig, fetch_dir: Path, stage_dir: Path) -> Path:
    fetch_dir = Path(fetch_dir)
    stage_dir = Path(stage_dir)
    images_dir = fetch_dir / "images"
    metadata_path = fetch_dir / "mapillary_metadata.parquet"
    annotated_dir = stage_dir / "annotated"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Stage 1 metadata not found at {metadata_path}. Run 'bfe fetch' first."
        )

    metadata = read_parquet(metadata_path)
    logger.info("Loaded %d image records from %s", len(metadata), metadata_path)

    device = resolve_device(cfg.detector.device)
    logger.info("YOLO inference device: %s", device)
    model = load_yolo_model(cfg.detector.weights)
    assert_target_class_supported(model, cfg.detector.target_class)

    predictions: list[dict] = []
    n_total = len(metadata)

    for idx, row in enumerate(metadata.itertuples(index=False), start=1):
        filename = str(row.image_filename)
        image_path = images_dir / filename
        building_id = str(row.building_id)

        base: dict[str, object] = {
            "building_id": building_id,
            "image_filename": filename,
            "windows_detected": 0,
            "floors": None,
            "floors_kmeans": None,
            "floors_gmm": None,
            "floors_dbscan": None,
            "height_m": None,
            "truncated_at_max_floors": False,
            "skipped_reason": None,
        }

        if not image_path.exists():
            base["skipped_reason"] = "image_missing"
            predictions.append(base)
            continue

        image = cv2.imread(str(image_path))
        if image is None:
            base["skipped_reason"] = "image_unreadable"
            predictions.append(base)
            continue

        window_boxes = detect_windows(model, image, cfg.detector, device)
        base["windows_detected"] = len(window_boxes)

        if len(window_boxes) <= cfg.floor_estimator.min_windows:
            base["skipped_reason"] = "below_min_windows"
            predictions.append(base)
            if idx % 50 == 0:
                logger.info(
                    "Detection progress: %d/%d (last: %s, %d windows, skipped)",
                    idx, n_total, filename, len(window_boxes),
                )
            continue

        estimate = estimate_floors(window_boxes)
        base.update(estimate.as_dict())

        reported_floors = estimate.floors
        truncated = reported_floors > cfg.floor_estimator.max_floors
        if truncated:
            reported_floors = cfg.floor_estimator.max_floors
        base["floors"] = reported_floors
        base["truncated_at_max_floors"] = truncated
        base["height_m"] = round(reported_floors * cfg.floor_estimator.avg_floor_height_m, 2)

        predictions.append(base)

        annotated = _annotate(image, window_boxes, reported_floors, base["height_m"])
        cv2.imwrite(str(annotated_dir / filename), annotated)

        if idx % 50 == 0:
            logger.info(
                "Detection progress: %d/%d (last: %s, %d windows, %s floors)",
                idx, n_total, filename, len(window_boxes), reported_floors,
            )

    predictions_path = stage_dir / "predictions.parquet"
    n_rows = write_parquet(predictions_path, predictions, PREDICTIONS_COLUMNS)

    scored = sum(1 for p in predictions if p["skipped_reason"] is None)
    truncated_count = sum(1 for p in predictions if p["truncated_at_max_floors"])
    logger.info(
        "Stage 2 complete: %d rows (%d scored, %d truncated) at %s",
        n_rows, scored, truncated_count, predictions_path,
    )
    return predictions_path


def _annotate(image, window_boxes, floors, height_m):  # type: ignore[no-untyped-def]
    annotated = image.copy()
    for (x1, y1, x2, y2) in window_boxes:
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
    height_str = f"{height_m:.1f} m" if height_m is not None else "n/a"
    text = f"Floors: {floors} | Height: {height_str} | Windows: {len(window_boxes)}"
    cv2.putText(
        annotated, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA
    )
    return annotated
