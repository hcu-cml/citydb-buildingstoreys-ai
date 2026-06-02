from __future__ import annotations

from typing import Any

from ..config import DetectorConfig

BBox = tuple[int, int, int, int]


def assert_target_class_supported(model, target_class: str) -> None:  # type: ignore[no-untyped-def]
    target = target_class.lower()
    names_attr: Any = getattr(model, "names", {})
    if isinstance(names_attr, dict):
        names_iter = names_attr.values()
    else:
        names_iter = names_attr
    available = {str(n).lower() for n in names_iter}
    if not available:
        return
    if target not in available:
        raise ValueError(
            f"Detector target_class={target_class!r} is not in the model's class list. "
            f"Available classes: {sorted(available)}"
        )


def detect_windows(
    model,  # type: ignore[no-untyped-def]
    image,  # type: ignore[no-untyped-def]
    cfg: DetectorConfig,
    device: str,
) -> list[BBox]:
    results = model.predict(
        source=image,
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
