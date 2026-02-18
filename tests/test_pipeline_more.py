from __future__ import annotations

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
        return [Article(title="A")]

    monkeypatch.setattr(pipeline_service, "collect_news", _fake_collect_news)
    rows = pipeline_service.fetch_news(hours=1, include_trending=True)
    assert rows


def test_extract_news_info_with_existing(monkeypatch, tmp_path):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    existing = [LLMEnrichedRow(Title="A", URL="https://example.com/a")]
    write_csv(records_from_llm_rows(existing), data_path("news_data_with_llm_info.csv"))

    def _fake_extract_from_rows(rows, model_name="gpt-4o"):
        return [type("R", (), {"result": ExtractionResult(short_summary="s")}) for _ in rows]

    monkeypatch.setattr(pipeline_service, "extract_from_rows", _fake_extract_from_rows)

    rows = [NewsRow(Title="B", URL="https://example.com/b", Description="D")]
    merged = pipeline_service.extract_news_info(rows)
    assert len(merged) == 2
