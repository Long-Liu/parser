import os
import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"


def setup():
    level = logging.DEBUG if os.getenv("APP_ENV", "local") == "local" else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    return logging.getLogger("parser")
