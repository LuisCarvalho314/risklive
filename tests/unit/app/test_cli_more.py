from __future__ import annotations

import sys

from app import cli as cli_app


def test_cli_extract(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "extract"])
    monkeypatch.setattr(cli_app, "read_csv", lambda path: [])
    monkeypatch.setattr(cli_app, "news_rows_from_records", lambda records: [])
    monkeypatch.setattr(cli_app, "extract_news_info", lambda rows: rows)
    cli_app.main()


def test_cli_topic(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "topic"])
    monkeypatch.setattr(cli_app, "read_csv", lambda path: [])
    monkeypatch.setattr(cli_app, "llm_rows_from_records", lambda records: [])
    monkeypatch.setattr(cli_app, "run_topic_modeling", lambda rows: None)
    cli_app.main()


def test_cli_report(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "report"])
    monkeypatch.setattr(cli_app, "read_csv", lambda path: [])
    monkeypatch.setattr(cli_app, "llm_rows_from_records", lambda records: [])
    monkeypatch.setattr(cli_app, "generate_report", lambda rows: [])
    cli_app.main()


def test_cli_dashboard(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "dashboard"])
    monkeypatch.setattr(cli_app, "export_dashboard", lambda: None)
    cli_app.main()


def test_cli_cleanup(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "cleanup", "--days", "1"])
    monkeypatch.setattr(cli_app, "cleanup_old_data", lambda days: 0)
    cli_app.main()
