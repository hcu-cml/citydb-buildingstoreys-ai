from __future__ import annotations

from pathlib import Path

from ..config import DetectorConfig

BBox = tuple[int, int, int, int]


def detect_windows(
    model,  # type: ignore[no-untyped-def]
    image_path: Path,
    cfg: DetectorConfig,
    device: str,
) -> list[BBox]:
    results = model.predict(
        source=str(image_path),
        conf=cfg.confidence_threshold,
        iou=cfg.iou_threshold,
        device=device,
        verbose=False,
    )

    boxes: list[BBox] = []
    target = cfg.target_class.lower()
    for result in results:
        names = getattr(result, "names", {})
        if result.boxes is None:
            continue
        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = str(names.get(class_id, "")).lower()
            if class_name != target:
                continue
            coords = box.xyxy[0].detach().cpu().numpy()
            x1, y1, x2, y2 = map(int, coords)
            boxes.append((x1, y1, x2, y2))
    return boxes
