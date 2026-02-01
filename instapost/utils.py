"""Utility functions for instapost."""

import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_json(filepath):
    """Load JSON from a file relative to PROJECT_ROOT."""
    full_path = PROJECT_ROOT / filepath
    if full_path.exists():
        with open(full_path, 'r') as f:
            return json.load(f)
    return []


def save_json(filepath, data):
    """Save data as JSON to a file relative to PROJECT_ROOT."""
    full_path = PROJECT_ROOT / filepath
    with open(full_path, 'w') as f:
        json.dump(data, f, indent=2)


def setup_logging(name: str, log_level=logging.INFO) -> logging.Logger:
    """Set up a logger with the given name.

    Args:
        name: Name of the logger
        log_level: Logging level (default: logging.INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
