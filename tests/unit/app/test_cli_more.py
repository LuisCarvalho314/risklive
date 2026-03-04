"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import sys
from types import SimpleNamespace

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


def test_cli_replay_week(monkeypatch):
    calls = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "risklive",
            "replay-week",
            "--days",
            "7",
            "--hours",
            "24",
            "--trending",
            "1",
            "--anchor-date",
            "2026-02-27",
            "--run-seca",
            "1",
            "--run-cleanup",
            "1",
        ],
    )
    monkeypatch.setitem(
        sys.modules,
        "services.replay",
        SimpleNamespace(run_replay_days=lambda **kwargs: calls.append(kwargs)),
    )
    cli_app.main()
    assert calls == [
        {
            "days": 7,
            "hours": 24,
            "include_trending": True,
            "anchor_date": "2026-02-27",
            "run_seca": True,
            "run_cleanup": True,
        }
    ]
