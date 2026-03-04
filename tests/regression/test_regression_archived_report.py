"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import pytest

from models.report import ReportEntry
from services import pipeline as pipeline_service
from services.storage import data_path, read_csv
from tests.fixtures.archive_loader import (
    extract_archive_to_workspace,
    latest_backup_archive,
    stage_backup_csvs_to_data,
)
from tests.fixtures.contracts import assert_report_contract
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


def test_generate_report_from_archived_data(monkeypatch, tmp_path):
    archive = latest_backup_archive()
    backup_dir = extract_archive_to_workspace(archive, tmp_path)
    stage_backup_csvs_to_data(tmp_path, backup_dir)

    records = read_csv(data_path("df_with_response_and_topics.csv"))
    rows = llm_rows_from_records(records)
    rows = sorted(rows, key=lambda row: (row.topic is None, row.topic))

    expected_topics = sorted({int(row.topic) for row in rows if row.alert_flag == "Red" and row.topic is not None})

    monkeypatch.setattr(pipeline_service, "generate_reports_from_rows", _stub_reports_from_rows)
    reports = pipeline_service.generate_report(rows)

    report_path = data_path("df_report.csv")
    if expected_topics:
        assert len(reports) == len(expected_topics)
        out_rows = assert_report_contract(report_path)
        out_topics = sorted({int(row["topic"]) for row in out_rows})
        assert out_topics == expected_topics

        for row in out_rows:
            topic = int(row["topic"])
            assert row["keyword"] == f"topic-{topic}"
            assert row["response"] == f"response-{topic}"
    else:
        assert reports == []
        assert report_path.exists()
        assert report_path.read_text(encoding="utf-8") == ""
