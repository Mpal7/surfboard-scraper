from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_logger(name: str, log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Return a module-level logger with file + console handlers, configured once."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"{name.replace('.', '_')}_{timestamp}.log"

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
