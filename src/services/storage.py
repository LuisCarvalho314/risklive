from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import csv

from config.settings import ROOT_DIR, get_config


def _resolve_dir(path: str) -> Path:
    base = Path(path)
    return base if base.is_absolute() else ROOT_DIR / base


def get_data_dir() -> Path:
    cfg = get_config()
    return _resolve_dir(cfg.save_dir.get("CSV_DATA_DIR", "results/data"))


def get_backup_dir() -> Path:
    cfg = get_config()
    return _resolve_dir(cfg.save_dir.get("CSV_DATA_BACKUP_DIR", "results/backup_data"))


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(normalized_rows)
    return path


def data_path(filename: str) -> Path:
    return ensure_dir(get_data_dir()) / filename


def backup_path(filename: str) -> Path:
    return ensure_dir(get_backup_dir()) / filename


def load_if_exists(path: Path) -> Optional[list[dict]]:
    if path.exists():
        return read_csv(path)
    return None
