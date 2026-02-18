from __future__ import annotations

import pytest

from models.csv import LLMEnrichedRow, NewsRow
from services import pipeline as pipeline_service


def test_generate_report_requires_topic():
    rows = [LLMEnrichedRow(Title="A", AlertFlag="Red", ShortSummary="s1")]
    with pytest.raises(ValueError):
        pipeline_service.generate_report(rows)


def test_cleanup_old_data(monkeypatch, tmp_path):
    from config import settings as settings_module
    from services.storage import data_path, write_csv
    from utils.rows import records_from_llm_rows

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    rows = [
        LLMEnrichedRow(Title="A", Timestamp="2000-01-01T00:00:00Z"),
        LLMEnrichedRow(Title="B", Timestamp="2999-01-01T00:00:00Z"),
    ]
    write_csv(records_from_llm_rows(rows), data_path("news_data_with_llm_info.csv"))

    removed = pipeline_service.cleanup_old_data(days_to_keep=30)
    assert removed == 1
