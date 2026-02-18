from __future__ import annotations

from app import main as app_main


def test_app_run(monkeypatch):
    monkeypatch.setattr(app_main, "collect_news", lambda *args, **kwargs: [1, 2, 3])
    count = app_main.run(hours=1)
    assert count == 3
