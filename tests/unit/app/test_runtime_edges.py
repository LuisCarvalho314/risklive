from __future__ import annotations

import sys

import pytest

from app import cli as cli_app
from app import server as server_app


def test_server_unexpected_error_handler(monkeypatch):
    monkeypatch.setattr(server_app, "fetch_news", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    app = server_app.create_app()
    client = app.test_client()
    response = client.get("/trigger/regular")
    payload = response.get_json()
    assert response.status_code == 500
    assert payload["status"] == "error"
    assert payload["error"]["message"] == "Unexpected server error"


def test_cli_unexpected_error_exit(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["risklive", "fetch"])
    monkeypatch.setattr(cli_app, "fetch_news", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(SystemExit) as exc:
        cli_app.main()
    assert exc.value.code == 1
