from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app import cli as cli_app
from models.errors import AppError


def test_cli_app_error_and_full_branch(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "fetch"])

    class DummyAppError(AppError):
        def __init__(self):
            super().__init__(code="x", message="m", http_status=500)

    monkeypatch.setattr(cli_app, "fetch_news", lambda *args, **kwargs: (_ for _ in ()).throw(DummyAppError()))
    with pytest.raises(SystemExit) as exc:
        cli_app.main()
    assert exc.value.code == 1

    monkeypatch.setattr(sys, "argv", ["risklive", "full", "--hours", "2", "--trending", "1"])
    dummy_server = SimpleNamespace(manual_fetch_and_process=lambda **kwargs: None)
    monkeypatch.setitem(sys.modules, "app.server", dummy_server)
    monkeypatch.setattr(cli_app, "export_dashboard", lambda: None)
    cli_app.main()


def test_cli_visualize_branch(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "visualize"])
    monkeypatch.setattr(cli_app, "run_topic_visualizations", lambda: None)
    cli_app.main()
