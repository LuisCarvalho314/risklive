from __future__ import annotations

from models.article import Article
from models.csv import LLMEnrichedRow, NewsRow
from models.extraction import ExtractionResult
from models.tasks import TaskName, TaskRequest, TaskResult


def test_article_defaults():
    article = Article(title="T")
    assert article.title == "T"


def test_news_row_aliases():
    row = NewsRow(Title="A", URL="https://example.com/a")
    assert row.title == "A"


def test_llm_row_keywords_coercion():
    row = LLMEnrichedRow(Title="B", RelevantKeywords="alpha, beta")
    assert row.relevant_keywords == ["alpha", "beta"]


def test_extraction_result_defaults():
    result = ExtractionResult()
    assert result.short_summary == ""


def test_tasks_models():
    req = TaskRequest(task=TaskName.save_regular_news, params={"hours": 1})
    res = TaskResult(task=req.task, ok=True)
    assert res.ok is True
