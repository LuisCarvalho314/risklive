from __future__ import annotations

from models.article import Article
from models.csv import LLMEnrichedRow, NewsRow
from models.extraction import ExtractionResult
from models.report import ReportEntry
from services import pipeline as pipeline_service


def test_fetch_and_save_news(monkeypatch):
    def _fake_collect_news(*_args, **_kwargs):
        return [Article(title="A", url="https://example.com/a", description="D")]

    monkeypatch.setattr(pipeline_service, "collect_news", _fake_collect_news)

    rows = pipeline_service.fetch_news(hours=1, include_trending=False)
    assert isinstance(rows[0], NewsRow)


def test_extract_news_info(monkeypatch):
    def _fake_extract_from_rows(rows, model_name="gpt-4o"):
        return [
            type("R", (), {"result": ExtractionResult(short_summary="s")})
            for _ in rows
        ]

    monkeypatch.setattr(pipeline_service, "extract_from_rows", _fake_extract_from_rows)

    rows = [NewsRow(Title="T", URL="https://example.com", Description="D")]
    enriched = pipeline_service.extract_news_info(rows)
    assert isinstance(enriched[0], LLMEnrichedRow)


def test_generate_report(monkeypatch):
    def _fake_generate_reports_from_rows(rows, model_name="gpt-4o"):
        return [ReportEntry(keyword="k", input_prompt="p", response="r", topic=1)]

    monkeypatch.setattr(pipeline_service, "generate_reports_from_rows", _fake_generate_reports_from_rows)

    rows = [LLMEnrichedRow(Title="A", AlertFlag="Red", ShortSummary="s1", topic=1)]
    reports = pipeline_service.generate_report(rows)
    assert reports[0]["keyword"] == "k"
