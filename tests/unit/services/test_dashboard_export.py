"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import json
import runpy
from datetime import datetime, timedelta, timezone

import polars as pl

from services import dashboard_export as de


def _sample_df() -> pl.DataFrame:
    now = datetime.now(timezone.utc)
    return pl.DataFrame(
        [
            {
                "Title": "N Red",
                "URL": "https://example.com/n-red",
                "Description": "nuclear red",
                "Timestamp": (now - timedelta(hours=1)).isoformat(),
                "AlertFlag": "Red",
                "AlertReason": "risk",
                "NewsCategory": "nuclear",
                "ShortSummary": "summary",
                "Relevance": "Yes",
                "RelevantKeywords": "alpha,beta",
                "topic": "1",
            },
            {
                "Title": "N Yellow",
                "URL": "https://example.com/n-yellow",
                "Description": "nuclear yellow",
                "Timestamp": (now - timedelta(hours=2)).isoformat(),
                "AlertFlag": "Yellow",
                "AlertReason": "watch",
                "NewsCategory": "nuclear industry",
                "ShortSummary": "summary2",
                "Relevance": "Yes",
                "RelevantKeywords": "beta,gamma",
                "topic": "1",
            },
            {
                "Title": "Geo Red",
                "URL": "https://example.com/g-red",
                "Description": "geo red",
                "Timestamp": (now - timedelta(hours=3)).isoformat(),
                "AlertFlag": "Red",
                "AlertReason": "geo",
                "NewsCategory": "geopolitical",
                "ShortSummary": "summary3",
                "Relevance": "Yes",
                "RelevantKeywords": "delta",
                "topic": "2",
            },
        ]
    )


def test_safe_helpers():
    assert de._safe_str(None) == ""
    assert de._safe_str("x") == "x"
    assert de._safe_str(float("nan")) == ""
    assert de._safe_timestamp("2025-01-01T00:00:00+00:00") is not None
    assert de._safe_timestamp("2025-01-01T00:00:00") is not None
    assert de._safe_timestamp(float("nan")) is None
    assert de._safe_timestamp("bad-ts") is None


def test_empty_and_guard_branches(tmp_path, monkeypatch):
    base = tmp_path / "results" / "data"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        de,
        "_data_path",
        lambda filename, key="CSV_DATA_DIR", default="results/data/": base / filename,
    )
    assert de.load_news().is_empty()

    empty_df = pl.DataFrame()
    assert de._merge_topics(empty_df).is_empty()
    assert de._attach_topic_keywords(empty_df).is_empty()
    assert de._sort_by_alert_and_time(empty_df).is_empty()
    assert de.build_recent_alerts(empty_df).red == []
    assert de.build_flagged_alerts(empty_df).red == []

    with_flags_missing = pl.DataFrame([{"Title": "A", "Timestamp": "2024-01-01T00:00:00+00:00"}]).with_columns(
        pl.col("Timestamp").str.to_datetime(time_zone="UTC")
    )
    assert de._sort_by_alert_and_time(with_flags_missing).height == 1
    assert de.build_recent_alerts(with_flags_missing).red == []
    assert de.build_flagged_alerts(with_flags_missing).red == []
    newsmap = de.build_newsmap(with_flags_missing)
    assert newsmap.name == "All News"


def test_build_alerts_recent_flagged_newsmap():
    df = _sample_df()
    alerts = de.build_alerts(df)
    assert alerts.nuclear
    assert "geopolitical" in alerts.non_nuclear

    recent = de.build_recent_alerts(df.with_columns(pl.col("Timestamp").str.to_datetime(time_zone="UTC")))
    assert isinstance(recent.red, list)
    flagged = de.build_flagged_alerts(df.with_columns(pl.col("Timestamp").str.to_datetime(time_zone="UTC")))
    assert flagged.red

    newsmap = de.build_newsmap(df.with_columns(pl.col("Timestamp").str.to_datetime(time_zone="UTC")))
    assert newsmap.name == "All News"
    assert newsmap.children


def test_merge_topics_and_load_news(tmp_path, monkeypatch):
    base = tmp_path / "results" / "data"
    base.mkdir(parents=True, exist_ok=True)
    news_csv = base / "news_data_with_llm_info.csv"
    topics_csv = base / "df_with_response_and_topics.csv"

    news_csv.write_text(
        "Title,URL,Description,Timestamp,AlertFlag,AlertReason,NewsCategory,ShortSummary,Relevance,RelevantKeywords,topic\n"
        "A,https://example.com/a,d,2025-01-01T00:00:00+00:00,Red,r,nuclear,s,Yes,\"a,b\",\n"
    )
    topics_csv.write_text(
        "Title,URL,topic\n"
        "A,https://example.com/a,7\n"
    )

    monkeypatch.setattr(
        de,
        "_data_path",
        lambda filename, key="CSV_DATA_DIR", default="results/data/": base / filename,
    )
    loaded = de.load_news()
    assert not loaded.is_empty()
    assert "topic" in loaded.columns

    topics_csv.write_text("URL,bad\nhttps://example.com/a,7\n")
    loaded2 = de.load_news()
    assert not loaded2.is_empty()


def test_merge_topics_existing_and_keyword_empty_branches(tmp_path, monkeypatch):
    base = tmp_path / "results" / "data"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        de,
        "_data_path",
        lambda filename, key="CSV_DATA_DIR", default="results/data/": base / filename,
    )
    df = pl.DataFrame(
        [{"Title": "A", "URL": "https://a", "topic": "1", "RelevantKeywords": ", ,"}]
    )
    merged = de._merge_topics(df)
    assert merged.get_column("topic").to_list() == ["1"]
    attached = de._attach_topic_keywords(df)
    assert "topic_keyword" in attached.columns


def test_load_topics_and_tree(tmp_path, monkeypatch):
    data_base = tmp_path / "results" / "data"
    img_base = tmp_path / "results" / "images"
    data_base.mkdir(parents=True, exist_ok=True)
    img_base.mkdir(parents=True, exist_ok=True)
    (data_base / "df_report.csv").write_text("keyword,response\nk,r\n")
    (img_base / "topic_tree.txt").write_text("tree")

    def _path(filename, key="CSV_DATA_DIR", default="results/data/"):
        if key == "TOPIC_MODEL_IMAGE_DIR":
            return img_base / filename
        return data_base / filename

    monkeypatch.setattr(de, "_data_path", _path)
    topics = de.load_topics()
    assert topics and topics[0].keyword == "k"
    assert de.load_topic_tree() == "tree"

    (data_base / "df_report.csv").write_text("bad_col\nx\n")
    assert de.load_topics() == []
    (data_base / "df_report.csv").write_text("")
    assert de.load_topics() == []
    (img_base / "topic_tree.txt").unlink()
    assert de.load_topic_tree() == ""


def test_main_writes_dashboard_and_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(de, "ROOT", tmp_path)
    monkeypatch.setattr(de, "load_news", lambda: _sample_df().with_columns(pl.col("Timestamp").str.to_datetime(time_zone="UTC")))
    monkeypatch.setattr(de, "load_topics", lambda: [])
    monkeypatch.setattr(de, "load_topic_tree", lambda: "")

    de.main()

    dashboard_path = tmp_path / "results" / "web" / "dashboard.json"
    schema_path = tmp_path / "results" / "web" / "dashboard.schema.json"
    assert dashboard_path.exists()
    assert schema_path.exists()
    payload = json.loads(dashboard_path.read_text())
    assert "alerts" in payload and "newsmap" in payload


def test_alert_and_newsmap_guard_branches():
    df_no_alert = pl.DataFrame([{"Title": "A", "NewsCategory": "nuclear"}])
    alerts = de.build_alerts(df_no_alert)
    assert alerts.nuclear == []

    df_no_cat = pl.DataFrame(
        [{"Title": "A", "AlertFlag": "Red", "Timestamp": "2024-01-01T00:00:00+00:00"}]
    ).with_columns(pl.col("Timestamp").str.to_datetime(time_zone="UTC"))
    alerts2 = de.build_alerts(df_no_cat)
    assert alerts2.non_nuclear == {}

    recent = de.build_recent_alerts(df_no_cat)
    assert recent.red == []

    root = de.build_newsmap(df_no_alert)
    assert root.name == "All News"


def test_dashboard_export_main_module_block(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(de, "main", lambda: None)
    runpy.run_module("services.dashboard_export", run_name="__main__")
