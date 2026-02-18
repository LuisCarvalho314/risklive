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

    server_app.fetch_and_process(None)
