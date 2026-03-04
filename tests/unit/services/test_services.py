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

    monkeypatch.setattr(reporting_service, "generate_report_section", _fake_report)

    reports = reporting_service.generate_reports(["a", "b"])
    assert reports[0].response == "a"
