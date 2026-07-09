"""
Simple logging utility for the game.
"""

import logging
import sys


def setup_logger(name: str = "meccha_gomoku", level: int = logging.DEBUG) -> logging.Logger:
    """Create a logger that writes to stdout with a consistent format."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    return logger
