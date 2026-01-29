from __future__ import annotations

from typing import List

from agents.extraction.agent import extract, extract_record
from models.csv import NewsRow
from models.extraction import ExtractionRecord


def extract_from_texts(texts: List[str], model_name: str = "gpt-4o") -> List[ExtractionRecord]:
    records: List[ExtractionRecord] = []
    for text in texts:
        record = extract_record(text, model_name=model_name)
        records.append(record)
    return records


def extract_from_rows(rows: List[NewsRow], model_name: str = "gpt-4o") -> List[ExtractionRecord]:
    texts: List[str] = []
    for row in rows:
        title = row.title or ""
        desc = row.description or ""
        texts.append(f"{title}. {desc}")
    return extract_from_texts(texts, model_name=model_name)
