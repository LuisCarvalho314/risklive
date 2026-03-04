"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from app import server as server_app
from models.errors import ValidationError


def test_trigger_regular_returns_structured_error(monkeypatch):
    def _boom(hours, include_trending):
        raise ValidationError("bad request")

    monkeypatch.setattr(server_app, "fetch_news", _boom)

    app = server_app.create_app()
    client = app.test_client()

    response = client.get("/trigger/regular")
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "bad request"
    assert "X-Correlation-Id" in response.headers
