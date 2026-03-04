"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pathlib import Path

import pytest

from services import dashboard_export as dashboard_export_service
from services.storage import data_path, read_csv, write_csv
from tests.fixtures.archive_loader import (
    extract_archive_to_workspace,
    latest_backup_archive,
    stage_backup_csvs_to_data,
)
from tests.fixtures.contracts import assert_dashboard_contract
from utils.rows import llm_rows_from_records, records_from_llm_rows

pytestmark = pytest.mark.integration


def _patch_dashboard_paths(monkeypatch, tmp_root: Path, layout: dict[str, Path]) -> None:
    monkeypatch.setattr(dashboard_export_service, "ROOT", tmp_root)

    def _path(filename: str, key: str = "CSV_DATA_DIR", default: str = "results/data/"):
        if key == "TOPIC_MODEL_IMAGE_DIR":
            return layout["images_dir"] / filename
        return layout["data_dir"] / filename

    monkeypatch.setattr(dashboard_export_service, "_data_path", _path)


def test_dashboard_builds_when_no_reportable_red_topics(monkeypatch, tmp_path):
    archive = latest_backup_archive()
    backup_dir = extract_archive_to_workspace(archive, tmp_path)
    layout = stage_backup_csvs_to_data(tmp_path, backup_dir)

    rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
    for row in rows:
        row.alert_flag = "Yellow"
    write_csv(records_from_llm_rows(rows), data_path("df_with_response_and_topics.csv"))
    # Empty-but-valid report file.
    data_path("df_report.csv").write_text("", encoding="utf-8")
    (layout["images_dir"] / "topic_tree.txt").write_text("integration-tree", encoding="utf-8")

    _patch_dashboard_paths(monkeypatch, tmp_path, layout)
    dashboard_export_service.main()

    payload = assert_dashboard_contract(layout["web_dir"] / "dashboard.json")
    assert payload["topics"] == []


def test_dashboard_gracefully_handles_malformed_report_columns(monkeypatch, tmp_path):
    archive = latest_backup_archive()
    backup_dir = extract_archive_to_workspace(archive, tmp_path)
    layout = stage_backup_csvs_to_data(tmp_path, backup_dir)

    # Missing required keyword/response columns, load_topics should return [].
    (layout["data_dir"] / "df_report.csv").write_text("bad_col\nx\n", encoding="utf-8")
    (layout["images_dir"] / "topic_tree.txt").write_text("integration-tree", encoding="utf-8")

    _patch_dashboard_paths(monkeypatch, tmp_path, layout)
    dashboard_export_service.main()

    payload = assert_dashboard_contract(layout["web_dir"] / "dashboard.json")
    assert payload["topics"] == []
