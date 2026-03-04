"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pathlib import Path

import pytest

from models.report import ReportEntry
from services import dashboard_export as dashboard_export_service
from services import pipeline as pipeline_service
from services.storage import data_path, read_csv
from tests.fixtures.archive_loader import (
    extract_archive_to_workspace,
    latest_backup_archive,
    stage_backup_csvs_to_data,
)
from tests.fixtures.contracts import assert_csv_has_columns, assert_dashboard_contract
from utils.rows import llm_rows_from_records

pytestmark = pytest.mark.integration


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
    if any(row.alert_flag == "Red" and row.topic is not None for row in rows):
        monkeypatch.setattr(pipeline_service, "generate_reports_from_rows", _stub_reports_from_rows)
        pipeline_service.generate_report(rows)
    else:
        # No reportable groups; keep report contract shape for dashboard topic loading.
        (data_path("df_report.csv")).write_text(
            "topic,keyword,input_prompt,response\n0,archive-fallback,fallback,fallback\n",
            encoding="utf-8",
        )


def _patch_dashboard_paths(monkeypatch, tmp_root: Path, layout: dict[str, Path]) -> None:
    monkeypatch.setattr(dashboard_export_service, "ROOT", tmp_root)

    def _path(filename: str, key: str = "CSV_DATA_DIR", default: str = "results/data/"):
        if key == "TOPIC_MODEL_IMAGE_DIR":
            return layout["images_dir"] / filename
        return layout["data_dir"] / filename

    monkeypatch.setattr(dashboard_export_service, "_data_path", _path)


def test_pipeline_generates_report_and_dashboard_from_archived_data(monkeypatch, tmp_path):
    archive = latest_backup_archive()
    backup_dir = extract_archive_to_workspace(archive, tmp_path)
    layout = stage_backup_csvs_to_data(tmp_path, backup_dir)

    (layout["images_dir"] / "topic_tree.txt").write_text("integration-tree", encoding="utf-8")
    _ensure_report_file(monkeypatch)
    _patch_dashboard_paths(monkeypatch, tmp_path, layout)

    dashboard_export_service.main()

    report_rows = assert_csv_has_columns(
        layout["data_dir"] / "df_report.csv",
        ["topic", "keyword", "input_prompt", "response"],
    )
    assert report_rows

    dashboard = assert_dashboard_contract(layout["web_dir"] / "dashboard.json")
    assert (layout["web_dir"] / "dashboard.schema.json").exists()
    assert dashboard["newsmap"]["children"] or dashboard["alerts"]["nuclear"] or dashboard["alerts"]["non_nuclear"]
    assert isinstance(dashboard["topics"], list)
