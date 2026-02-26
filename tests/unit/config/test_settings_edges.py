from __future__ import annotations

import pytest

from config import settings as settings_module


def test_settings_load_config_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        settings_module.load_config(tmp_path / "does-not-exist.yml")
