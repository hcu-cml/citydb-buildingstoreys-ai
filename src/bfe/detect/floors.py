"""Storey-count estimation from detected window bounding boxes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.mixture import GaussianMixture

from ..logging import get_logger

logger = get_logger(__name__)

BBox = tuple[int, int, int, int]


@dataclass(frozen=True)
class FloorEstimate:
    floors: int
    floors_kmeans: int | None
    floors_gmm: int | None
    floors_dbscan: int | None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "floors": self.floors,
            "floors_kmeans": self.floors_kmeans,
            "floors_gmm": self.floors_gmm,
            "floors_dbscan": self.floors_dbscan,
        }


def estimate_floors(window_boxes: Sequence[BBox]) -> FloorEstimate:
    if len(window_boxes) == 0:
        return FloorEstimate(0, None, None, None)
    if len(window_boxes) < 3:
        return FloorEstimate(1, None, None, None)

    y_centers = np.array([(y1 + y2) / 2.0 for _, y1, _, y2 in window_boxes])
    y_centers.sort()
    vertical_gaps = np.diff(y_centers).reshape(-1, 1)

    floors_km = _floors_kmeans(vertical_gaps)
    floors_gmm = _floors_gmm(vertical_gaps)
    floors_db = _floors_dbscan(vertical_gaps, n_windows=len(window_boxes))

    final = _mode_of_three(floors_km, floors_gmm, floors_db)
    return FloorEstimate(final, floors_km, floors_gmm, floors_db)


def _mode_of_three(
    floors_km: int | None,
    floors_gmm: int | None,
    floors_db: int | None,
) -> int:
    candidates = [v for v in (floors_km, floors_gmm, floors_db) if v is not None and v >= 1]
    if not candidates:
        return 1
    counts = Counter(candidates)
    top_count = counts.most_common(1)[0][1]
    if top_count >= 2:
        for v in candidates:
            if counts[v] == top_count:
                return max(1, int(v))
    if floors_km is not None and floors_km >= 1:
        return max(1, int(floors_km))
    return max(1, int(candidates[0]))


def _floors_kmeans(vertical_gaps: np.ndarray) -> int | None:
    try:
        km = KMeans(n_clusters=2, n_init=10, random_state=42)
        labels = km.fit_predict(vertical_gaps)
        return _floors_from_two_cluster_labels(vertical_gaps, labels)
    except Exception as exc:  # noqa: BLE001
        logger.debug("KMeans floor estimate failed: %s", exc)
        return None


def _floors_gmm(vertical_gaps: np.ndarray) -> int | None:
    try:
        gmm = GaussianMixture(n_components=2, random_state=42, covariance_type="full")
        labels = gmm.fit_predict(vertical_gaps)
        return _floors_from_two_cluster_labels(vertical_gaps, labels)
    except Exception as exc:  # noqa: BLE001
        logger.debug("GMM floor estimate failed: %s", exc)
        return None


def _floors_dbscan(vertical_gaps: np.ndarray, n_windows: int) -> int | None:
    try:
        median_gap = float(np.median(vertical_gaps))
        eps_value = median_gap * 1.5 if median_gap > 0 else 10.0
        db = DBSCAN(eps=eps_value, min_samples=1)
        labels = db.fit_predict(vertical_gaps)
        unique = set(labels.tolist())
        unique.discard(-1)
        if len(unique) < 2:
            return None
        cluster_means = {
            label: float(vertical_gaps[labels == label].mean()) for label in unique
        }
        inter_floor_label = max(cluster_means, key=cluster_means.get)
        inter_floor_gaps = int(np.sum(labels == inter_floor_label))
        return inter_floor_gaps + 1
    except Exception as exc:  # noqa: BLE001
        logger.debug("DBSCAN floor estimate failed: %s", exc)
        return None


def _floors_from_two_cluster_labels(vertical_gaps: np.ndarray, labels: np.ndarray) -> int:
    cluster_0 = vertical_gaps[labels == 0]
    cluster_1 = vertical_gaps[labels == 1]
    mean_0 = float(cluster_0.mean()) if len(cluster_0) else 0.0
    mean_1 = float(cluster_1.mean()) if len(cluster_1) else 0.0
    inter_floor_label = 0 if mean_0 > mean_1 else 1
    inter_floor_gaps = int(np.sum(labels == inter_floor_label))
    return inter_floor_gaps + 1
