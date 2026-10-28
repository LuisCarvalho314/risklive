"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from app import server as server_app


def test_fetch_and_process(monkeypatch):
    monkeypatch.setattr(server_app, "fetch_news", lambda hours, include_trending: [])
    monkeypatch.setattr(server_app, "save_news", lambda rows: rows)
    monkeypatch.setattr(server_app, "read_csv", lambda path: [])
    monkeypatch.setattr(server_app, "news_rows_from_records", lambda records: [])
    monkeypatch.setattr(server_app, "llm_rows_from_records", lambda records: [])
    monkeypatch.setattr(server_app, "extract_news_info", lambda rows: rows)
    monkeypatch.setattr(server_app, "run_topic_modeling", lambda rows: None)
    monkeypatch.setattr(server_app, "generate_report", lambda rows: [])
    monkeypatch.setattr(server_app, "export_dashboard", lambda: None)
    monkeypatch.setattr(server_app, "run_seca_light_timeline", lambda: None)

    server_app.fetch_and_process(None)


def test_fetch_and_process_order(monkeypatch):
    calls = []
    monkeypatch.setattr(
        server_app,
        "manual_fetch_and_process",
        lambda **kwargs: calls.append("manual"),
    )
    monkeypatch.setattr(server_app, "export_dashboard", lambda: calls.append("dashboard"))
    monkeypatch.setattr(server_app, "run_seca_light_timeline", lambda: calls.append("seca"))

    server_app.fetch_and_process(None)

    assert calls == ["manual", "dashboard"]


def test_fetch_and_process_does_not_invoke_retired_v1(monkeypatch):
    monkeypatch.setattr(server_app, "manual_fetch_and_process", lambda **kwargs: None)
    monkeypatch.setattr(server_app, "export_dashboard", lambda: None)

    def _boom():
        raise AssertionError("retired V1 was invoked")

    monkeypatch.setattr(server_app, "run_seca_light_timeline", _boom)

    server_app.fetch_and_process(None)


def test_manual_fetch_and_process_failure_branch(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(server_app, "fetch_news", _boom)

    try:
        server_app.manual_fetch_and_process()
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")
