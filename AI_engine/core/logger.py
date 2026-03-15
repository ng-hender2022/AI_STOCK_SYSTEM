"""
AI_STOCK Logging Module
Log format: [TIMESTAMP] [LEVEL] [COMPONENT] message
Theo DATA_PIPELINE_SPEC.
"""

import logging
import sys
from pathlib import Path

from .config import LOG_DIR, LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVEL

_initialized = False


def _ensure_log_dir():
    """Tạo log directory nếu chưa có."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str, log_file: str = None) -> logging.Logger:
    """
    Tạo logger cho một component.

    Args:
        name: Logger name (e.g., "V4RSI", "R1", "pipeline", "x1")
        log_file: Optional log file name. Default: ai_stock.log

    Usage:
        logger = get_logger("V4RSI")
        logger.info("Computing RSI for VNM")
        logger.warning("Missing data for date 2026-03-14")
        logger.error("Failed to write signals.db")
    """
    global _initialized

    logger = logging.getLogger(f"ai_stock.{name}")

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL))
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    _ensure_log_dir()
    file_name = log_file or "ai_stock.log"
    file_handler = logging.FileHandler(
        LOG_DIR / file_name, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
