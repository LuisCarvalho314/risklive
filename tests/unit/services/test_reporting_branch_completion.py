from __future__ import annotations

from models.csv import LLMEnrichedRow
from models.report import ReportEntry
from services import reporting as reporting_service


def test_reporting_continue_branches(monkeypatch):
    monkeypatch.setattr(reporting_service, "rate_limit_sleep", lambda: None)
    monkeypatch.setattr(
        reporting_service,
        "generate_report_section",
        lambda text, model_name="gpt-4o": ReportEntry(keyword="k", input_prompt=text, response="r"),
    )
    rows = [
        LLMEnrichedRow(Title="A", AlertFlag="Yellow", topic=1, ShortSummary="x"),
        LLMEnrichedRow(Title="B", AlertFlag="Red", topic=None, ShortSummary="y"),
    ]
    assert reporting_service.generate_reports_from_rows(rows) == []
