from __future__ import annotations

from services import ingestion as ingestion_service


def test_collect_news(monkeypatch):
    monkeypatch.setattr(ingestion_service, "fetch_news", lambda **_: ["a"])
    items = ingestion_service.collect_news(["q"], hours=1)
    assert items == ["a"]
