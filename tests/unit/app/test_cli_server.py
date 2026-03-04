"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import sys

from app import cli as cli_app
from app import server as server_app


def test_cli_fetch(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "fetch"])

    monkeypatch.setattr(cli_app, "fetch_news", lambda hours, include_trending: [])
    monkeypatch.setattr(cli_app, "save_news", lambda rows: rows)

    cli_app.main()


def test_server_routes(monkeypatch):
    monkeypatch.setattr(server_app, "fetch_news", lambda hours, include_trending: [])
    monkeypatch.setattr(server_app, "save_news", lambda rows: rows)
    monkeypatch.setattr(server_app, "extract_news_info", lambda rows: rows)
    monkeypatch.setattr(server_app, "run_topic_modeling", lambda rows: None)
    monkeypatch.setattr(server_app, "generate_report", lambda rows: [])
    monkeypatch.setattr(server_app, "export_dashboard", lambda: None)
    monkeypatch.setattr(server_app, "cleanup_old_data", lambda days: 0)
    monkeypatch.setattr(server_app, "read_csv", lambda path: [])

    app = server_app.create_app()
    client = app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/trigger/regular").status_code == 200
    assert client.get("/trigger/trending").status_code == 200
    assert client.get("/trigger/extract").status_code == 200
    assert client.get("/trigger/topic").status_code == 200
    assert client.get("/trigger/report").status_code == 200
    assert client.get("/trigger/dashboard").status_code == 200
    assert client.get("/trigger/cleanup").status_code == 200
