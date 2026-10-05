"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pathlib import Path

import pytest

from models.csv import LLMEnrichedRow
from services import pipeline as pipeline_service
from services import storage as storage_service


def test_storage_empty_write_and_load_if_exists(tmp_path):
    out = tmp_path / "empty.csv"
    storage_service.write_csv([], out)
    assert out.read_text() == ""
    assert storage_service.load_if_exists(tmp_path / "missing.csv") is None


def test_pipeline_continue_branches(monkeypatch, tmp_path, caplog):
    rows = [
        LLMEnrichedRow(Title="B", AlertFlag="Red", topic=1, ShortSummary="y"),
        LLMEnrichedRow(Title="A", AlertFlag="Red", topic=None, ShortSummary="x"),
    ]
    with monkeypatch.context() as report_patches:
        report_patches.setattr(
            pipeline_service,
            "generate_reports_from_rows",
            lambda group: [type("R", (), {"keyword": "k", "input_prompt": "p", "response": "r"})()],
        )
        report_patches.setattr(pipeline_service, "write_csv", lambda *args, **kwargs: None)
        report_patches.setattr(pipeline_service, "data_path", lambda filename: filename)
        reports = pipeline_service.generate_report(rows)
        assert reports and reports[0]["topic"] == 1

    # The shared settings fixture resolves storage beneath this test's tmp_path.
    path = storage_service.data_path("invalid_timestamp.csv")
    assert path.is_relative_to(tmp_path)
    storage_service.write_csv([{"Title": "bad", "Timestamp": "bad"}], path)
    assert pipeline_service.cleanup_old_data(1) == 1
    assert storage_service.read_csv(path) == []
    invalid_logs = [
        record for record in caplog.records
        if getattr(record, "event", "") == "cleanup_invalid_timestamps_dropped"
    ]
    assert len(invalid_logs) == 1
    assert invalid_logs[0].dropped_invalid_timestamp_rows == 1


def test_storage_write_oserror_branch(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_service, "ensure_dir", lambda path: path)
    monkeypatch.setattr(
        Path,
        "open",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(OSError("boom")),
    )
    with pytest.raises(Exception):
        storage_service.write_csv([{"a": 1}], tmp_path / "x.csv")
