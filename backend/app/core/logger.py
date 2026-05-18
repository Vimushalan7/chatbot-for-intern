"""
logger.py
---------
Centralised logging configuration.
Import `logger` from this module everywhere in the backend.
"""

import logging
import sys


def get_logger(name: str = "research_assistant") -> logging.Logger:
    """Return a pre-configured logger instance."""
    logger = logging.getLogger(name)

    if not logger.handlers:  # avoid duplicate handlers on re-import
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Shared logger instance
logger = get_logger()
