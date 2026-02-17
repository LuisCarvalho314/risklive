from __future__ import annotations

import logging
import os
from pathlib import Path


def get_project_root() -> Path:
    # If this file is src/utils/logging.py, then:
    # __file__ -> .../risklive/src/utils/logging.py
    # parents[2] -> .../risklive
    return Path(__file__).resolve().parents[2]


def configure_logging(project_root: Path | None = None) -> None:
    """
    Configure logging to both console and logs/app.log.
    Call once at process startup (e.g., in cli.py main()).
    """
    root = project_root or get_project_root()

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = (logs_dir / "app.log").resolve()

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if configure_logging() is called more than once
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            existing_path = Path(getattr(handler, "baseFilename", "")).resolve()
            if existing_path == log_file_path:
                return

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
