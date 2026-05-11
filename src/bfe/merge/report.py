from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ..config import PipelineConfig
from ..logging import get_logger
from .join import join_predictions

logger = get_logger(__name__)


def run_merge(cfg: PipelineConfig, detect_dir: Path, stage_dir: Path) -> Path:
    detect_dir = Path(detect_dir)
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    predictions_path = detect_dir / "predictions.parquet"
    if not predictions_path.exists():
        raise FileNotFoundError(
            f"Stage 2 predictions not found at {predictions_path}. Run 'bfe detect' first."
        )

    merged = join_predictions(cfg, predictions_path)

    geojson_path = stage_dir / "buildings_with_predictions.geojson"
    merged.to_file(geojson_path, driver="GeoJSON")

    csv_path = stage_dir / "buildings_with_predictions.csv"
    merged.drop(columns="geometry").to_csv(csv_path, index=False)

    summary = _build_summary(merged)
    (stage_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    _write_distribution_plot(merged, stage_dir / "predicted_floors_distribution.png")

    logger.info(
        "Stage 3 complete: %s (%d features, %d with predictions)",
        geojson_path,
        summary["total_buildings"],
        summary["with_predictions"],
    )
    return geojson_path


def _build_summary(merged) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    total = int(len(merged))
    with_pred = int(merged["predicted_floors"].notna().sum())
    truncated = int(merged["truncated_at_max_floors"].fillna(False).sum())

    distribution = (
        merged["predicted_floors"].dropna().astype(int).value_counts().sort_index().to_dict()
    )
    distribution = {int(k): int(v) for k, v in distribution.items()}

    comparison: dict[str, Any] = {}
    if "height_storeys" in merged.columns:
        both = merged.dropna(subset=["height_storeys", "predicted_floors"])
        if len(both) > 0:
            diff = both["predicted_floors"].astype(float) - both["height_storeys"].astype(float)
            comparison = {
                "n_compared": int(len(both)),
                "exact_match": int((diff == 0).sum()),
                "mean_absolute_error": float(diff.abs().mean()),
                "median_absolute_error": float(diff.abs().median()),
                "rmse": float(((diff) ** 2).mean() ** 0.5),
            }

    return {
        "total_buildings": total,
        "with_predictions": with_pred,
        "without_predictions": total - with_pred,
        "truncated_at_max_floors": truncated,
        "predicted_floor_distribution": distribution,
        "ground_truth_comparison": comparison,
    }


def _write_distribution_plot(merged, path: Path) -> None:  # type: ignore[no-untyped-def]
    series = merged["predicted_floors"].dropna().astype(int)
    if series.empty:
        return

    counts = series.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(counts.index.astype(str), counts.values, color="steelblue")
    ax.set_xlabel("Predicted number of floors")
    ax.set_ylabel("Building count")
    ax.set_title("Predicted floor distribution")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
