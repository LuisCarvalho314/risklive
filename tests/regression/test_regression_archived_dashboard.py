"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import pytest

from models.report import ReportEntry
from services import dashboard_export as dashboard_export_service
from services import pipeline as pipeline_service
from services.storage import data_path, read_csv, write_csv
from tests.fixtures.archive_loader import (
    extract_archive_to_workspace,
    latest_backup_archive,
    stage_backup_csvs_to_data,
)
from tests.fixtures.contracts import assert_csv_has_columns, assert_dashboard_contract
from utils.rows import llm_rows_from_records

pytestmark = pytest.mark.regression


def _stub_reports_from_rows(group):
    topic = int(group[0].topic)
    return [
        ReportEntry(
            topic=topic,
            keyword=f"topic-{topic}",
            input_prompt=f"prompt-{topic}",
            response=f"response-{topic}",
        )
    ]


def _ensure_report_file(monkeypatch) -> None:
    rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
    rows = sorted(rows, key=lambda row: (row.topic is None, row.topic))
    if not any(row.alert_flag == "Red" and row.topic is not None for row in rows):
        write_csv(
            [{"topic": 0, "keyword": "archive-fallback", "input_prompt": "fallback", "response": "fallback"}],
            data_path("df_report.csv"),
        )
        return
    monkeypatch.setattr(pipeline_service, "generate_reports_from_rows", _stub_reports_from_rows)
    pipeline_service.generate_report(rows)


def test_dashboard_export_from_archived_data(monkeypatch, tmp_path):
    archive = latest_backup_archive()
    backup_dir = extract_archive_to_workspace(archive, tmp_path)
    layout = stage_backup_csvs_to_data(tmp_path, backup_dir)

    _ensure_report_file(monkeypatch)

    topic_tree_path = layout["images_dir"] / "topic_tree.txt"
    topic_tree_path.write_text("archived-tree", encoding="utf-8")

    monkeypatch.setattr(dashboard_export_service, "ROOT", tmp_path)

    def _path(filename: str, key: str = "CSV_DATA_DIR", default: str = "results/data/"):
        if key == "TOPIC_MODEL_IMAGE_DIR":
            return layout["images_dir"] / filename
        return layout["data_dir"] / filename

    monkeypatch.setattr(dashboard_export_service, "_data_path", _path)
    dashboard_export_service.main()

    report_rows = assert_csv_has_columns(
        layout["data_dir"] / "df_report.csv",
        ["topic", "keyword", "input_prompt", "response"],
    )
    assert report_rows

    dashboard_path = layout["web_dir"] / "dashboard.json"
    schema_path = layout["web_dir"] / "dashboard.schema.json"
    payload = assert_dashboard_contract(dashboard_path)
    assert schema_path.exists()

    assert payload["alerts"]["nuclear"] or payload["alerts"]["non_nuclear"]
    assert payload["newsmap"]["children"]

    if payload["topics"]:
        first_topic = payload["topics"][0]
        assert "keyword" in first_topic
        assert "response" in first_topic
