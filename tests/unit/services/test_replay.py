from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import pytest

from models.errors import ValidationError
from services import replay as replay_service


def test_build_day_anchors_for_week():
    anchors = replay_service._build_day_anchors(days=7, anchor=date(2026, 2, 27))
    assert len(anchors) == 7
    assert anchors[0].isoformat() == "2026-02-21T07:00:00+00:00"
    assert anchors[-1].isoformat() == "2026-02-27T07:00:00+00:00"


def test_parse_anchor_date_validation():
    with pytest.raises(ValidationError):
        replay_service._parse_anchor_date("2026/02/27")


def test_run_replay_days_order_and_reference_time(monkeypatch):
    calls = []
    refs = []

    monkeypatch.setattr(replay_service, "fetch_news", lambda **kwargs: refs.append(kwargs["reference_now_utc"]) or [])
    monkeypatch.setattr(replay_service, "save_news", lambda rows: calls.append("save"))
    monkeypatch.setattr(replay_service, "read_csv", lambda path: [])
    monkeypatch.setattr(replay_service, "news_rows_from_records", lambda rows: [])
    monkeypatch.setattr(replay_service, "extract_news_info", lambda rows: calls.append("extract"))
    monkeypatch.setattr(replay_service, "llm_rows_from_records", lambda rows: [])
    monkeypatch.setattr(replay_service, "run_topic_modeling", lambda rows: calls.append("topic"))
    monkeypatch.setattr(replay_service, "generate_report", lambda rows: calls.append("report"))
    monkeypatch.setattr(replay_service, "export_dashboard", lambda: calls.append("dashboard"))
    monkeypatch.setattr(replay_service, "run_seca_light_timeline", lambda: calls.append("seca"))
    monkeypatch.setattr(
        replay_service,
        "cleanup_old_data",
        lambda days, reference_now_utc=None: calls.append(("cleanup", reference_now_utc)),
    )
    monkeypatch.setattr(replay_service, "data_path", lambda name: name)
    monkeypatch.setattr(replay_service, "get_config", lambda: type("Cfg", (), {"cleanup_days_to_keep": 3})())

    replay_service.run_replay_days(
        days=2,
        hours=24,
        include_trending=True,
        anchor_date="2026-02-27",
        run_seca=True,
        run_cleanup=True,
    )

    assert [dt.isoformat() for dt in refs] == [
        "2026-02-26T07:00:00+00:00",
        "2026-02-27T07:00:00+00:00",
    ]
    assert calls == [
        "save",
        "extract",
        "topic",
        "report",
        "dashboard",
        "seca",
        ("cleanup", refs[0]),
        "save",
        "extract",
        "topic",
        "report",
        "dashboard",
        "seca",
        ("cleanup", refs[1]),
    ]


def test_run_replay_days_without_seca_and_cleanup(monkeypatch):
    monkeypatch.setattr(replay_service, "fetch_news", lambda **kwargs: [])
    monkeypatch.setattr(replay_service, "save_news", lambda rows: None)
    monkeypatch.setattr(replay_service, "read_csv", lambda path: [])
    monkeypatch.setattr(replay_service, "news_rows_from_records", lambda rows: [])
    monkeypatch.setattr(replay_service, "extract_news_info", lambda rows: None)
    monkeypatch.setattr(replay_service, "llm_rows_from_records", lambda rows: [])
    monkeypatch.setattr(replay_service, "run_topic_modeling", lambda rows: None)
    monkeypatch.setattr(replay_service, "generate_report", lambda rows: [])
    monkeypatch.setattr(replay_service, "export_dashboard", lambda: None)
    monkeypatch.setattr(replay_service, "run_seca_light_timeline", lambda: (_ for _ in ()).throw(AssertionError("should not run")))
    monkeypatch.setattr(
        replay_service,
        "cleanup_old_data",
        lambda days, reference_now_utc=None: (_ for _ in ()).throw(AssertionError("should not run")),
    )
    monkeypatch.setattr(replay_service, "data_path", lambda name: name)
    monkeypatch.setattr(replay_service, "get_config", lambda: type("Cfg", (), {"cleanup_days_to_keep": 3})())

    replay_service.run_replay_days(
        days=1,
        hours=24,
        include_trending=False,
        anchor_date="2026-02-27",
        run_seca=False,
        run_cleanup=False,
    )


def test_run_replay_days_sets_replay_log_context(monkeypatch):
    captured = []

    @contextmanager
    def _fake_log_context(**kwargs):
        captured.append(kwargs)
        yield

    monkeypatch.setattr(replay_service, "log_context", _fake_log_context)
    monkeypatch.setattr(replay_service, "fetch_news", lambda **kwargs: [])
    monkeypatch.setattr(replay_service, "save_news", lambda rows: None)
    monkeypatch.setattr(replay_service, "read_csv", lambda path: [])
    monkeypatch.setattr(replay_service, "news_rows_from_records", lambda rows: [])
    monkeypatch.setattr(replay_service, "extract_news_info", lambda rows: None)
    monkeypatch.setattr(replay_service, "llm_rows_from_records", lambda rows: [])
    monkeypatch.setattr(replay_service, "run_topic_modeling", lambda rows: None)
    monkeypatch.setattr(replay_service, "generate_report", lambda rows: [])
    monkeypatch.setattr(replay_service, "export_dashboard", lambda: None)
    monkeypatch.setattr(replay_service, "data_path", lambda name: name)
    monkeypatch.setattr(replay_service, "get_config", lambda: type("Cfg", (), {"cleanup_days_to_keep": 3})())

    replay_service.run_replay_days(days=1, anchor_date="2026-02-27", run_seca=False, run_cleanup=False)

    assert captured and captured[0]["replay_mode"] is True
    assert captured[0]["replay_day"] == "2026-02-27"
    assert captured[0]["replay_index"] == 1
    assert captured[0]["replay_total_days"] == 1
    assert captured[0]["replay_anchor_date"] == "2026-02-27"
