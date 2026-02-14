import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) is True


def app_base_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def human_readable_size(bytes_count: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_count)
    for unit in units:
        if size < 1000.0:
            return f"{size:.2f} {unit}"
        size /= 1000.0
    return f"{size:.2f} PB"


def setup_logging() -> None:
    logger = logging.getLogger("video_compressor")
    if logger.handlers:
        return
    logger.setLevel(logging.DEBUG)

    log_path = app_base_dir() / "video_compressor.log"
    try:
        file_handler = RotatingFileHandler(
            str(log_path), maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)
    except Exception:
        pass

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_fmt = logging.Formatter("%(name)s %(levelname)s %(message)s")
    stderr_handler.setFormatter(stderr_fmt)
    logger.addHandler(stderr_handler)
