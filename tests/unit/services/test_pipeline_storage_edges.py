from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from models.csv import LLMEnrichedRow
from services import pipeline as pipeline_service
from services import storage as storage_service


def test_storage_empty_write_and_load_if_exists(tmp_path):
    out = tmp_path / "empty.csv"
    storage_service.write_csv([], out)
    assert out.read_text() == ""
    assert storage_service.load_if_exists(tmp_path / "missing.csv") is None


def test_pipeline_continue_branches(monkeypatch):
    rows = [
        LLMEnrichedRow(Title="B", AlertFlag="Red", topic=1, ShortSummary="y"),
        LLMEnrichedRow(Title="A", AlertFlag="Red", topic=None, ShortSummary="x"),
    ]
    monkeypatch.setattr(
        pipeline_service,
        "generate_reports_from_rows",
        lambda group: [type("R", (), {"keyword": "k", "input_prompt": "p", "response": "r"})()],
    )
    monkeypatch.setattr(pipeline_service, "write_csv", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline_service, "data_path", lambda filename: filename)
    reports = pipeline_service.generate_report(rows)
    assert reports and reports[0]["topic"] == 1

    bad_ts = SimpleNamespace(timestamp="bad")
    monkeypatch.setattr(pipeline_service, "load_if_exists", lambda path: [{"Title": "bad", "Timestamp": "bad"}])
    monkeypatch.setattr(pipeline_service, "llm_rows_from_records", lambda records: [bad_ts])
    monkeypatch.setattr(pipeline_service, "records_from_llm_rows", lambda rows: rows)
    monkeypatch.setattr(pipeline_service, "write_csv", lambda *args, **kwargs: None)
    assert pipeline_service.cleanup_old_data(1) == 1


def test_storage_write_oserror_branch(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_service, "ensure_dir", lambda path: path)
    monkeypatch.setattr(
        Path,
        "open",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(OSError("boom")),
    )
    with pytest.raises(Exception):
        storage_service.write_csv([{"a": 1}], tmp_path / "x.csv")
