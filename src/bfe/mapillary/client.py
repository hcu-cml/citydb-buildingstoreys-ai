from __future__ import annotations

import os
import time
from typing import Any, Iterable

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import BBox
from ..logging import get_logger

logger = get_logger(__name__)

GRAPH_URL = "https://graph.mapillary.com/images"
DEFAULT_FIELDS: tuple[str, ...] = (
    "id",
    "captured_at",
    "geometry",
    "compass_angle",
    "thumb_1024_url",
    "thumb_2048_url",
)


class MapillaryAuthError(RuntimeError):
    pass


class MapillaryAPIError(RuntimeError):
    pass


def get_access_token() -> str:
    token = os.environ.get("MAPILLARY_ACCESS_TOKEN", "").strip()
    if not token:
        raise MapillaryAuthError(
            "MAPILLARY_ACCESS_TOKEN is not set. "
            "Obtain one at https://www.mapillary.com/developer."
        )
    return token


class MapillaryClient:
    def __init__(
        self,
        *,
        limit: int = 2000,
        timeout_s: float = 30.0,
        max_pages_per_cell: int = 20,
        per_page_sleep_s: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        self._token = get_access_token()
        self._limit = limit
        self._timeout_s = timeout_s
        self._max_pages = max_pages_per_cell
        self._per_page_sleep = per_page_sleep_s
        self._session = session or requests.Session()

    def fetch_bbox(self, bbox: BBox, fields: Iterable[str] = DEFAULT_FIELDS) -> list[dict]:
        params: dict[str, Any] = {
            "access_token": self._token,
            "bbox": bbox.as_string(),
            "limit": self._limit,
            "fields": ",".join(fields),
        }

        results: list[dict] = []
        page_count = 0
        next_url: str | None = None
        next_params: dict[str, Any] | None = params

        while page_count < self._max_pages:
            payload = self._request_page(next_url, next_params)
            results.extend(payload.get("data", []) or [])
            paging = payload.get("paging") or {}
            next_url = paging.get("next")
            page_count += 1
            if not next_url:
                break
            next_params = None
            if self._per_page_sleep > 0:
                time.sleep(self._per_page_sleep)
        else:
            logger.warning(
                "Reached max_pages_per_cell=%d for bbox %s; results may be truncated",
                self._max_pages,
                bbox.as_string(),
            )

        return results

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.Timeout, requests.ConnectionError, MapillaryAPIError)
        ),
    )
    def _request_page(self, url: str | None, params: dict[str, Any] | None) -> dict:
        target = url or GRAPH_URL
        response = self._session.get(target, params=params, timeout=self._timeout_s)
        status = response.status_code

        if status == 200:
            return response.json()
        if status in (401, 403):
            raise MapillaryAuthError(f"Mapillary auth rejected (HTTP {status})")
        if status >= 500 or status == 429:
            raise MapillaryAPIError(f"Transient Mapillary error (HTTP {status})")
        raise MapillaryAPIError(f"Mapillary API error (HTTP {status}): {response.text[:200]}")
