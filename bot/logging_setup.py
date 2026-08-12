"""Logging configuration."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logging with a clear, production-friendly format.

    Production guidance (LOG_LEVEL=INFO): handlers must log structured metadata
    only (user_id, action, outcome). Do not log message text, movie titles,
    file_id values, or full admin ID lists at INFO or above.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)

    # Keep third-party noise down unless we're debugging.
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if log_level <= logging.DEBUG else logging.WARNING
    )
