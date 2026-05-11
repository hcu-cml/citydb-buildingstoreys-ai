from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..logging import get_logger

logger = get_logger(__name__)


def resolve_device(preference: Literal["auto", "cpu", "cuda"]) -> str:
    if preference == "cpu":
        return "cpu"

    try:
        import torch

        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False

    if preference == "cuda":
        if not cuda_available:
            raise RuntimeError("device='cuda' requested but no CUDA device is available")
        return "cuda:0"

    return "cuda:0" if cuda_available else "cpu"


def load_yolo_model(weights: Path):  # type: ignore[no-untyped-def]
    from ultralytics import YOLO

    weights = Path(weights)
    if not weights.exists():
        raise FileNotFoundError(
            f"YOLO weights not found at {weights}. "
            "Place the .pt file there or set 'detector.weights' in the config."
        )

    logger.info("Loading YOLO weights from %s", weights)
    return YOLO(str(weights))
