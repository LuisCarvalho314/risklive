from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import csv

from config import settings as settings_module
from models.errors import StorageError
from utils.logging import get_logger

logger = get_logger(__name__)


def _resolve_dir(path: str) -> Path:
    base = Path(path)
    return base if base.is_absolute() else settings_module.ROOT_DIR / base


def get_data_dir() -> Path:
    cfg = settings_module.get_config()
    return _resolve_dir(cfg.save_dir.get("CSV_DATA_DIR", "results/data"))


def get_backup_dir() -> Path:
    cfg = settings_module.get_config()
    return _resolve_dir(cfg.save_dir.get("CSV_DATA_BACKUP_DIR", "results/backup_data"))


def ensure_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError as exc:
        raise StorageError("Unable to create directory", details={"path": str(path)}) from exc


def read_csv(path: Path) -> list[dict]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader)
    except OSError as exc:
        raise StorageError("Unable to read CSV file", details={"path": str(path)}) from exc


def write_csv(rows: Iterable[dict], path: Path) -> Path:
    ensure_dir(path.parent)
    rows = list(rows)
    if not rows:
        path.write_text("")
        return path
    normalized_rows: list[dict] = []
    for row in rows:
        normalized: dict = {}
        for key, value in row.items():
            if isinstance(value, list):
                normalized[key] = ", ".join([str(item) for item in value if str(item).strip()])
            else:
                normalized[key] = value
        normalized_rows.append(normalized)
    fieldnames: list[str] = []
    for row in normalized_rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    try:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(normalized_rows)
    except OSError as exc:
        raise StorageError("Unable to write CSV file", details={"path": str(path)}) from exc
    logger.debug(
        "csv_written",
        extra={"event": "csv_written", "component": "services.storage", "operation": "write_csv"},
    )
    return path


def data_path(filename: str) -> Path:
    return ensure_dir(get_data_dir()) / filename


def backup_path(filename: str) -> Path:
    return ensure_dir(get_backup_dir()) / filename


def load_if_exists(path: Path) -> Optional[list[dict]]:
    if path.exists():
        return read_csv(path)
    return None
