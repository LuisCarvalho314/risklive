"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from app import server as server_app


def test_server_full_route_and_main(monkeypatch):
    monkeypatch.setattr(server_app, "manual_fetch_and_process", lambda **kwargs: None)
    monkeypatch.setattr(server_app, "cleanup_old_data", lambda days: 0)
    app = server_app.create_app()
    client = app.test_client()
    resp = client.get("/trigger/full?hours=3&trending=0")
    assert resp.status_code == 200
    assert resp.get_json()["trending"] is False

    class DummyApp:
        def run(self, **kwargs):
            return None

    monkeypatch.setattr(server_app, "create_app", lambda: DummyApp())
    monkeypatch.setattr(server_app, "start_scheduler", lambda app: None)
    server_app.main()
