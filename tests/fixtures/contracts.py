"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pathlib import Path
import csv
import json


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def assert_csv_has_columns(path: Path, required_columns: list[str]) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    assert rows, f"CSV has no data rows: {path}"
    row_keys = set(rows[0].keys())
    missing = [column for column in required_columns if column not in row_keys]
    assert not missing, f"Missing columns in {path}: {missing}"
    return rows


def assert_report_contract(path: Path) -> list[dict[str, str]]:
    rows = assert_csv_has_columns(path, ["topic", "keyword", "input_prompt", "response"])
    for row in rows:
        assert str(row["topic"]).strip() != ""
        assert str(row["keyword"]).strip() != ""
        assert str(row["response"]).strip() != ""
    return rows


def assert_dashboard_contract(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required_top_level = [
        "generated_at",
        "alerts",
        "recent_alerts",
        "flagged_alerts",
        "newsmap",
        "topics",
        "topic_tree",
    ]
    for key in required_top_level:
        assert key in payload, f"Missing dashboard key: {key}"
    assert isinstance(payload["topics"], list)
    assert payload["newsmap"].get("name") == "All News"
    return payload
