"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app import server as server_app
from config.settings import ServerConfig


pytestmark = pytest.mark.usefixtures("isolated_app")


def test_server_full_route_and_main(monkeypatch):
    fetch_and_process = Mock()
    monkeypatch.setattr(server_app, "fetch_and_process", fetch_and_process)
    app = server_app.create_app()
    client = app.test_client()
    resp = client.get("/trigger/full?hours=3&trending=0")
    assert resp.status_code == 200
    assert resp.get_json()["trending"] is False
    assert resp.get_json()["hours"] == 3
    fetch_and_process.assert_called_once_with(app)

    class DummyApp:
        def run(self, **kwargs):
            return None

    monkeypatch.setattr(server_app, "create_app", lambda: DummyApp())
    monkeypatch.setattr(server_app, "start_scheduler", lambda app: None)
    monkeypatch.setattr(
        server_app, "get_server_config",
        lambda: ServerConfig(host="127.0.0.1", port=5101, disable_scheduler=False),
    )
    server_app.main()
