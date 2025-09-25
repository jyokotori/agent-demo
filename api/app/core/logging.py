"""Logging configuration helpers."""
from __future__ import annotations

import logging

from app.core.config import Settings

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(settings: Settings) -> None:
    """Configure application-wide logging using the provided settings."""

    level_name = settings.log_level.upper()
    level: int
    if level_name in logging._nameToLevel:  # type: ignore[attr-defined]
        level = logging._nameToLevel[level_name]  # type: ignore[attr-defined]
    else:
        level = logging.INFO

    logging.basicConfig(level=level, format=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    logging.getLogger("httpx").setLevel(max(logging.WARNING, level))
