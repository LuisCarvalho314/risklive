from __future__ import annotations

import logging

from models.article import Article
from models.csv import LLMEnrichedRow, NewsRow
from models.extraction import ExtractionResult
from services import pipeline as pipeline_service
from services.storage import data_path, write_csv
from utils.rows import records_from_llm_rows, records_from_news_rows


def test_save_news_merges(monkeypatch, tmp_path):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    existing = [NewsRow(Title="A", URL="https://example.com/a")]
    write_csv(records_from_news_rows(existing), data_path("news_data.csv"))

    rows = [NewsRow(Title="B", URL="https://example.com/b")]
    merged = pipeline_service.save_news(rows)
    assert len(merged) == 2


def test_dedupe_helpers():
    a = NewsRow(Title="A", URL="https://example.com/a")
    b = NewsRow(Title="A2", URL="https://example.com/a")
    deduped = pipeline_service._dedupe_rows([a, b], lambda r: pipeline_service._url_key(r.url))
    assert len(deduped) == 1


def test_fetch_news_includes_trending(monkeypatch):
    def _fake_collect_news(queries, hours):
        assert "TrendA" in queries
        return [Article(title="A", source_price=0.42)]

    monkeypatch.setattr(pipeline_service, "collect_news", _fake_collect_news)
    rows = pipeline_service.fetch_news(hours=1, include_trending=True)
    assert rows
    assert rows[0].source_price == 0.42


def test_extract_news_info_with_existing(monkeypatch, tmp_path):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    existing = [LLMEnrichedRow(Title="A", URL="https://example.com/a")]
    write_csv(records_from_llm_rows(existing), data_path("news_data_with_llm_info.csv"))

    def _fake_extract_from_rows(rows, model_name="gpt-4o"):
        return [type("R", (), {"result": ExtractionResult(short_summary="s")}) for _ in rows]

    monkeypatch.setattr(pipeline_service, "extract_from_rows", _fake_extract_from_rows)

    rows = [NewsRow(Title="B", URL="https://example.com/b", Description="D", Source_Price=0.11)]
    merged = pipeline_service.extract_news_info(rows)
    assert len(merged) == 2
    by_url = {str(row.url): row for row in merged}
    assert by_url["https://example.com/b"].source_price == 0.11


def test_save_news_backfills_missing_source_price(monkeypatch, tmp_path):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    existing = [NewsRow(Title="A", URL="https://example.com/a", Source_Price=None)]
    write_csv(records_from_news_rows(existing), data_path("news_data.csv"))
    merged = pipeline_service.save_news([NewsRow(Title="A-dup", URL="https://example.com/a", Source_Price=0.07)])
    assert len(merged) == 1
    assert merged[0].source_price == 0.07


def test_save_news_emits_stage_and_artifact_logs(monkeypatch, tmp_path, caplog):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    rows = [NewsRow(Title="B", URL="https://example.com/b")]
    with caplog.at_level(logging.INFO):
        pipeline_service.save_news(rows)

    events = [getattr(record, "event", "") for record in caplog.records]
    assert "pipeline_stage_start" in events
    assert "pipeline_stage_end" in events
    assert "artifact_written" in events


def test_extract_news_info_skips_when_no_todo(monkeypatch, tmp_path, caplog):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    existing = [LLMEnrichedRow(Title="A", URL="https://example.com/a")]
    write_csv(records_from_llm_rows(existing), data_path("news_data_with_llm_info.csv"))

    rows = [NewsRow(Title="A", URL="https://example.com/a", Description="D", Source_Price=0.09)]
    with caplog.at_level(logging.INFO):
        out = pipeline_service.extract_news_info(rows)

    assert len(out) == 1
    assert out[0].source_price == 0.09
    end_logs = [r for r in caplog.records if getattr(r, "event", "") == "pipeline_stage_end"]
    assert end_logs
    assert getattr(end_logs[-1], "stage_status", "") == "skipped"
