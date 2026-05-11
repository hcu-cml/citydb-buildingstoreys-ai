from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

EARTH_RADIUS_M = 6_371_000.0


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, lam1, phi2, lam2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlam = lam2 - lam1
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    bearing = math.atan2(x, y)
    return (math.degrees(bearing) + 360.0) % 360.0


def angle_difference(angle1: float, angle2: float) -> float:
    diff = abs(angle1 - angle2) % 360.0
    return min(diff, 360.0 - diff)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, lam1, phi2, lam2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dphi = phi2 - phi1
    dlam = lam2 - lam1
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class MatchedImage:
    image_id: str
    lat: float
    lon: float
    bearing: float
    distance_m: float
    bearing_diff_deg: float
    captured_at: Any
    thumb_url: str | None


def match_images_to_building(
    building_lat: float,
    building_lon: float,
    images: Iterable[dict],
    search_radius_m: float,
    bearing_tolerance_deg: float,
    max_images: int,
) -> list[MatchedImage]:
    candidates: list[MatchedImage] = []

    for img in images:
        geom = img.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        img_lon, img_lat = float(coords[0]), float(coords[1])

        compass = img.get("compass_angle")
        if compass is None:
            continue

        dist = haversine_distance(building_lat, building_lon, img_lat, img_lon)
        if dist > search_radius_m:
            continue

        expected = calculate_bearing(img_lat, img_lon, building_lat, building_lon)
        bearing_diff = angle_difference(float(compass), expected)
        if bearing_diff > bearing_tolerance_deg:
            continue

        thumb = img.get("thumb_2048_url") or img.get("thumb_1024_url")
        candidates.append(
            MatchedImage(
                image_id=str(img.get("id")),
                lat=img_lat,
                lon=img_lon,
                bearing=float(compass),
                distance_m=dist,
                bearing_diff_deg=bearing_diff,
                captured_at=img.get("captured_at"),
                thumb_url=thumb,
            )
        )

    candidates.sort(key=lambda m: (m.bearing_diff_deg, m.distance_m))
    return candidates[:max_images]
