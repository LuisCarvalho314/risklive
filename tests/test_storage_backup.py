from __future__ import annotations

from services.storage import backup_path


def test_backup_path(tmp_path, monkeypatch):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    path = backup_path("b.csv")
    assert path.name == "b.csv"
    assert path.parent.exists()
