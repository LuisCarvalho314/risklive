"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import pytest

from config import settings as settings_module


def test_settings_load_config_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        settings_module.load_config(tmp_path / "does-not-exist.yml")


@pytest.mark.parametrize(
    "environment, expected",
    [
        ({}, ("0.0.0.0", 5001, False)),
        ({"HOST": "127.0.0.1"}, ("127.0.0.1", 5001, False)),
        ({"PORT": "5101"}, ("0.0.0.0", 5101, False)),
        ({"DISABLE_SCHEDULER": "true"}, ("0.0.0.0", 5001, True)),
        ({"DISABLE_SCHEDULER": "false"}, ("0.0.0.0", 5001, False)),
    ],
)
def test_server_config_environment(monkeypatch, environment, expected):
    # Prevent inherited environment or checkout .env from affecting defaults.
    monkeypatch.setattr(settings_module, "_load_environment_variables", lambda: None)
    for name in ("HOST", "PORT", "DISABLE_SCHEDULER"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    config = settings_module.get_server_config()

    assert (config.host, config.port, config.disable_scheduler) == expected
    assert type(config.port) is int
    assert type(config.disable_scheduler) is bool


def test_server_config_model_defaults():
    config = settings_module.ServerConfig()
    assert config.host == "0.0.0.0"
    assert config.port == 5001
    assert config.disable_scheduler is False
