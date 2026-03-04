"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from models.csv import LLMEnrichedRow, NewsRow
from models.dashboard import AlertItem
from models.errors import AppError, from_exception


def test_csv_and_dashboard_none_validators():
    row = NewsRow(Title="A", URL=None, Timestamp=None)
    assert row.url is None
    assert row.timestamp is None

    enriched = LLMEnrichedRow(Title="A", RelevantKeywords=None)
    assert enriched.relevant_keywords == []

    item = AlertItem(title="A", url=None, timestamp=None)
    assert item.url is None
    assert item.timestamp is None


def test_csv_keyword_validator_remaining_branches():
    row = LLMEnrichedRow(Title="A", RelevantKeywords="[a,b")
    assert row.relevant_keywords == ["a", "b"]
    row2 = LLMEnrichedRow(Title="B", RelevantKeywords=123)
    assert row2.relevant_keywords == ["123"]


def test_from_exception_app_error_passthrough():
    err = AppError(code="x", message="m")
    assert from_exception(err) is err
