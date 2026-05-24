import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = os.getenv("LOG_FILE", "logs/slms.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 500 * 1024))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("slms")
logger.setLevel(LOG_LEVEL)

# Prevent duplicate handlers when module is imported multiple times.
if not logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def configure_logging() -> None:
    """Ensure the logger is configured before app startup."""
    logger.debug(
        "Logging configured (level=%s, file=%s, max_bytes=%s, backups=%s)",
        LOG_LEVEL,
        LOG_FILE,
        LOG_MAX_BYTES,
        LOG_BACKUP_COUNT,
    )
