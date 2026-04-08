"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from models.csv import LLMEnrichedRow, NewsRow
from models.extraction import ExtractionResult
from models.report import ReportEntry
from services import extraction as extraction_service
from services import reporting as reporting_service


def test_extract_from_rows(monkeypatch):
    def _fake_extract_record(text: str, model_name: str = "gpt-4o"):
        return type("R", (), {"input_text": text, "result": ExtractionResult(short_summary=text), "metrics": None})

    monkeypatch.setattr(extraction_service, "extract_record", _fake_extract_record)

    rows = [NewsRow(Title="T", Description="D")]
    records = extraction_service.extract_from_rows(rows)
    assert records[0].result.short_summary.startswith("T")


def test_generate_reports_from_rows(monkeypatch):
    def _fake_report(text: str, model_name: str = "gpt-4o"):
        return ReportEntry(keyword="k", input_prompt="p", response="r")

    monkeypatch.setattr(reporting_service, "rate_limit_sleep", lambda: None)
    monkeypatch.setattr(reporting_service, "generate_report_section", _fake_report)

    rows = [
        LLMEnrichedRow(Title="A", AlertFlag="Red", ShortSummary="s1", topic=1),
        LLMEnrichedRow(Title="B", AlertFlag="Red", ShortSummary="s2", topic=1),
    ]
    reports = reporting_service.generate_reports_from_rows(rows)
    assert reports[0].topic == 1


def test_generate_reports(monkeypatch):
    def _fake_report(text: str, model_name: str = "gpt-4o"):
        return ReportEntry(keyword="k", input_prompt="p", response=text)

    monkeypatch.setattr(reporting_service, "rate_limit_sleep", lambda: None)
    monkeypatch.setattr(reporting_service, "generate_report_section", _fake_report)

    reports = reporting_service.generate_reports(["a", "b"])
    assert reports[0].response == "a"


def test_generate_reports_from_rows_chunks_and_merges(monkeypatch):
    calls: list[tuple[str, str]] = []

    def _fake_report(text: str, model_name: str = "gpt-4o"):
        calls.append(("chunk", text))
        return ReportEntry(keyword="chunk-keyword", input_prompt=text, response=f"partial:{text}")

    def _fake_merge(text: str, model_name: str = "gpt-4o"):
        calls.append(("merge", text))
        return ReportEntry(keyword="merged-keyword", input_prompt=text, response="merged-response")

    monkeypatch.setattr(reporting_service, "REPORT_CHUNK_CHAR_BUDGET", 10)
    monkeypatch.setattr(reporting_service, "rate_limit_sleep", lambda: None)
    monkeypatch.setattr(reporting_service, "generate_report_section", _fake_report)
    monkeypatch.setattr(reporting_service, "generate_merged_report_section", _fake_merge)

    rows = [
        LLMEnrichedRow(Title="A", AlertFlag="Red", ShortSummary="alpha beta", topic=1),
        LLMEnrichedRow(Title="B", AlertFlag="Red", ShortSummary="gamma delta", topic=1),
    ]

    reports = reporting_service.generate_reports_from_rows(rows)

    assert reports == [
        ReportEntry(keyword="merged-keyword", input_prompt=calls[-1][1], response="merged-response", topic=1)
    ]
    assert [kind for kind, _ in calls[:-1]] == ["chunk", "chunk", "chunk"]
    assert calls[-1][0] == "merge"
    assert "Chunk Report 1" in calls[-1][1]
    assert "partial:alpha beta" in calls[-1][1]
    assert "partial:gamma" in calls[-1][1]


def test_build_topic_report_chunks_preserves_order_and_uses_title_fallback():
    rows = [
        LLMEnrichedRow(Title="fallback title", AlertFlag="Red", ShortSummary="", topic=1),
        LLMEnrichedRow(Title="ignored", AlertFlag="Red", ShortSummary="abc def", topic=1),
    ]

    chunks = reporting_service.build_topic_report_chunks(rows, char_budget=12)

    assert chunks == ["fallback", "title", "abc def"]
