"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from models.csv import LLMEnrichedRow, NewsRow
from utils.rows import (
    llm_rows_from_records,
    news_rows_from_records,
    records_from_llm_rows,
    records_from_news_rows,
)


def test_news_rows_roundtrip():
    records = [{"Title": "A", "URL": "https://example.com/a"}]
    rows = news_rows_from_records(records)
    out = records_from_news_rows(rows)
    assert out[0]["Title"] == "A"


def test_llm_rows_roundtrip():
    records = [{"Title": "B", "RelevantKeywords": "alpha, beta"}]
    rows = llm_rows_from_records(records)
    assert isinstance(rows[0], LLMEnrichedRow)
    out = records_from_llm_rows(rows)
    assert out[0]["RelevantKeywords"] == ["alpha", "beta"]
