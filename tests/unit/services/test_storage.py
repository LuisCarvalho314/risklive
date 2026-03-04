"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from services.storage import data_path, read_csv, write_csv


def test_write_read_csv(tmp_path, monkeypatch):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    path = data_path("test.csv")
    rows = [{"A": "1", "B": "2"}, {"A": "3", "B": "4"}]
    write_csv(rows, path)
    loaded = read_csv(path)
    assert loaded[0]["A"] == "1"
