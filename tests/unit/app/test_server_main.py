from unittest.mock import Mock

import pytest

from app import server as server_app
from config.settings import ServerConfig


@pytest.mark.parametrize("disabled", [False, True])
def test_main_respects_server_config(monkeypatch, disabled):
    config = ServerConfig(
        host="127.0.0.1", port=5101, disable_scheduler=disabled
    )
    app = Mock()
    start_scheduler = Mock()
    monkeypatch.setattr(server_app, "configure_logging", lambda: None)
    monkeypatch.setattr(server_app, "get_server_config", lambda: config)
    monkeypatch.setattr(server_app, "create_app", lambda: app)
    monkeypatch.setattr(server_app, "start_scheduler", start_scheduler)

    server_app.main()

    if disabled:
        start_scheduler.assert_not_called()
    else:
        start_scheduler.assert_called_once_with(app)
    app.run.assert_called_once_with(host="127.0.0.1", port=5101)
