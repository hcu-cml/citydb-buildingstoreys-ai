from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from rich.logging import RichHandler

_CONFIGURED = False


def configure_logging(level: Optional[str] = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = (level or os.environ.get("BFE_LOG_LEVEL") or "INFO").upper()
    numeric = getattr(logging, resolved, logging.INFO)

    handler: logging.Handler
    if sys.stderr.isatty():
        handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
            markup=False,
        )
        fmt = "%(message)s"
    else:
        handler = logging.StreamHandler(sys.stderr)
        fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"

    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric)

    for noisy in ("urllib3", "PIL", "matplotlib", "fiona", "rasterio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
