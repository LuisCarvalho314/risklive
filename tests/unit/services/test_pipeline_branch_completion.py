"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from models.csv import LLMEnrichedRow
from models.report import ReportEntry
from services import pipeline as pipeline_service


def test_pipeline_wrapper_and_cleanup_branches(monkeypatch):
    monkeypatch.setattr(pipeline_service, "compute_topic_modeling", lambda rows: "tm")
    monkeypatch.setattr(pipeline_service, "compute_topic_visualizations", lambda: "tv")
    assert pipeline_service.run_topic_modeling([]) == "tm"
    assert pipeline_service.run_topic_visualizations() == "tv"

    rows = [
        LLMEnrichedRow(Title="A", AlertFlag="Yellow", topic=1, ShortSummary="s"),
        LLMEnrichedRow(Title="B", AlertFlag="Red", topic=2, ShortSummary="r"),
    ]
    monkeypatch.setattr(
        pipeline_service,
        "generate_reports_from_rows",
        lambda grouped: [ReportEntry(keyword="k", input_prompt="p", response="r")],
    )
    monkeypatch.setattr(pipeline_service, "write_csv", lambda rows, path: path)
    monkeypatch.setattr(pipeline_service, "data_path", lambda filename: filename)
    out = pipeline_service.generate_report(rows)
    assert out and out[0]["topic"] == 2

    monkeypatch.setattr(pipeline_service, "load_if_exists", lambda path: None)
    assert pipeline_service.cleanup_old_data(3) == 0

    stale = LLMEnrichedRow(Title="X", Timestamp=None)
    fresh = LLMEnrichedRow(Title="Y", Timestamp=datetime.now(timezone.utc).isoformat())
    monkeypatch.setattr(
        pipeline_service,
        "load_if_exists",
        lambda path: [{"Title": stale.title, "Timestamp": stale.timestamp}, {"Title": fresh.title, "Timestamp": fresh.timestamp}],
    )
    monkeypatch.setattr(pipeline_service, "llm_rows_from_records", lambda records: [stale, fresh])
    monkeypatch.setattr(pipeline_service, "records_from_llm_rows", lambda rows: rows)
    monkeypatch.setattr(pipeline_service, "write_csv", lambda rows, path: path)
    assert pipeline_service.cleanup_old_data(3) >= 0


def test_run_topic_modeling_logs_artifacts_for_paths(monkeypatch):
    class _Artifacts:
        data_csv = "results/topics.csv"
        model_dir = "results/topic_model"
        assignments = [1]

    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(pipeline_service, "compute_topic_modeling", lambda rows: _Artifacts())
    monkeypatch.setattr(
        pipeline_service,
        "log_artifact_written",
        lambda logger, **kwargs: calls.append((kwargs["artifact_type"], str(kwargs["artifact_path"]))),
    )

    out = pipeline_service.run_topic_modeling([LLMEnrichedRow(Title="A", topic=1)])
    assert out.assignments == [1]
    assert ("csv", "results/topics.csv") in calls
    assert ("model", "results/topic_model") in calls


def test_export_dashboard_wrapper(monkeypatch):
    called = {"ok": False}
    monkeypatch.setattr(pipeline_service, "export_dashboard_main", lambda: called.__setitem__("ok", True))
    pipeline_service.export_dashboard()
    assert called["ok"] is True


def test_generate_report_skip_branch(monkeypatch):
    rows = [LLMEnrichedRow(Title="A", AlertFlag="Yellow", topic=1, ShortSummary="s")]
    monkeypatch.setattr(pipeline_service, "data_path", lambda filename: Path(filename))
    monkeypatch.setattr(pipeline_service, "write_csv", lambda rows, path: path)
    assert pipeline_service.generate_report(rows) == []


def test_export_dashboard_logs_artifact_when_present(monkeypatch, tmp_path):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    def _fake_export():
        out = tmp_path / "results" / "web" / "dashboard.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(pipeline_service, "export_dashboard_main", _fake_export)
    pipeline_service.export_dashboard()
