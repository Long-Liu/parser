from __future__ import annotations

# Application-wide logging configuration.

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"


def setup(debug: bool = True):
    """Configure root logger — DEBUG in local mode, INFO otherwise."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
