"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from models.csv import LLMEnrichedRow, NewsRow
from models.dashboard import AlertItem
from models.errors import (
    AppError,
    ExternalServiceError,
    NotFoundError,
    ProcessingError,
    RateLimitError,
    StorageError,
    ValidationError,
    from_exception,
)


def test_news_row_and_alert_item_empty_values():
    row = NewsRow(Title="t", URL="none", Timestamp="nan", Source_Price="none")
    assert row.url is None
    assert row.timestamp is None
    assert row.source_price is None

    alert = AlertItem(title="a", url="none", timestamp="none")
    assert alert.url is None
    assert alert.timestamp is None


def test_llm_enriched_row_keyword_and_numeric_coercion():
    row = LLMEnrichedRow(
        Title="t",
        RelevantKeywords="['a', 'b']",
        LLM_Price="none",
        PromptTokens="",
        CompletionTokens="nan",
        TotalTokens="3",
        Source_Price="0.02",
        topic="4",
    )
    assert row.relevant_keywords == ["a", "b"]
    assert row.llm_price is None
    assert row.prompt_tokens is None
    assert row.completion_tokens is None
    assert row.total_tokens == 3
    assert row.source_price == 0.02
    assert row.topic == 4


def test_error_types_and_factory():
    app_error = AppError(code="x", message="m")
    assert str(app_error) == "x: m"
    assert isinstance(ValidationError("bad"), AppError)
    assert isinstance(StorageError("io"), AppError)
    assert isinstance(ProcessingError("proc"), AppError)
    assert isinstance(NotFoundError("missing"), AppError)
    assert isinstance(RateLimitError("slow"), AppError)
    assert isinstance(ExternalServiceError("svc"), AppError)
    converted = from_exception(RuntimeError("boom"))
    assert converted.code == "processing_error"
