from __future__ import annotations

from typing import Iterable, List

from models.csv import LLMEnrichedRow, NewsRow


def news_rows_from_records(records: Iterable[dict]) -> List[NewsRow]:
    return [NewsRow(**record) for record in records]


def llm_rows_from_records(records: Iterable[dict]) -> List[LLMEnrichedRow]:
    return [LLMEnrichedRow(**record) for record in records]


def records_from_news_rows(rows: Iterable[NewsRow]) -> List[dict]:
    return [row.model_dump(by_alias=True) for row in rows]


def records_from_llm_rows(rows: Iterable[LLMEnrichedRow]) -> List[dict]:
    return [row.model_dump(by_alias=True) for row in rows]
