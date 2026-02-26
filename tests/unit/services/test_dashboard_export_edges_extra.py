from __future__ import annotations

from pathlib import Path

import polars as pl

from services import dashboard_export as dashboard_export_service


def test_dashboard_export_remaining_branches(monkeypatch):
    assert dashboard_export_service._safe_timestamp(None) is None
    assert dashboard_export_service._safe_timestamp(object()) is None

    no_ts = pl.DataFrame([{"Title": "A"}])
    recent = dashboard_export_service.build_recent_alerts(no_ts)
    assert isinstance(recent.red, list)

    newsmap = dashboard_export_service.build_newsmap(
        pl.DataFrame([{"Title": "A", "AlertFlag": "Red", "NewsCategory": "nuclear"}])
    )
    assert newsmap.name == "All News"

    base = Path("tmp_topics.csv")
    monkeypatch.setattr(dashboard_export_service, "_data_path", lambda *_args, **_kwargs: base)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(
        dashboard_export_service.pl,
        "read_csv",
        lambda _p: pl.DataFrame([{"URL": "https://example.com/a", "topic": "1"}]),
    )
    df = pl.DataFrame([{"URL": "https://example.com/a", "topic": "1"}])
    out = dashboard_export_service._merge_topics(df)
    assert out.get_column("topic").to_list() == ["1"]


def test_dashboard_newsmap_empty_category_branch(monkeypatch):
    original_filter = dashboard_export_service.pl.DataFrame.filter
    state = {"first": True}

    def _fake_filter(self, *args, **kwargs):
        if state["first"]:
            state["first"] = False
            return dashboard_export_service.pl.DataFrame(schema=self.schema)
        return original_filter(self, *args, **kwargs)

    monkeypatch.setattr(dashboard_export_service.pl.DataFrame, "filter", _fake_filter)
    df = pl.DataFrame([{"NewsCategory": "nuclear", "AlertFlag": "Red", "Title": "A"}])
    root = dashboard_export_service.build_newsmap(df)
    assert root.name == "All News"


def test_merge_topics_title_fallback_branch(monkeypatch):
    monkeypatch.setattr(
        dashboard_export_service,
        "_data_path",
        lambda *_args, **_kwargs: Path("topics.csv"),
    )
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(
        dashboard_export_service.pl,
        "read_csv",
        lambda _p: pl.DataFrame([{"Title": "A", "topic": "7"}]),
    )
    df = pl.DataFrame([{"Title": "A", "topic": "", "RelevantKeywords": "x,y"}])
    merged = dashboard_export_service._merge_topics(df)
    assert merged.get_column("topic").to_list() == ["7"]
