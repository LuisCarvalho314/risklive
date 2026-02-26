from __future__ import annotations

import pytest

from tests.fixtures.archive_loader import (
    extract_archive_to_workspace,
    latest_backup_archive,
    stage_backup_csvs_to_data,
)
from tests.fixtures.contracts import assert_csv_has_columns

pytestmark = pytest.mark.regression


def test_archived_dataset_contracts(tmp_path):
    archive = latest_backup_archive()
    backup_dir = extract_archive_to_workspace(archive, tmp_path)
    layout = stage_backup_csvs_to_data(tmp_path, backup_dir)

    news_rows = assert_csv_has_columns(
        layout["data_dir"] / "news_data.csv",
        ["Title", "URL", "Timestamp"],
    )
    llm_rows = assert_csv_has_columns(
        layout["data_dir"] / "news_data_with_llm_info.csv",
        ["Title", "URL", "AlertFlag", "RelevantKeywords"],
    )
    topic_rows = assert_csv_has_columns(
        layout["data_dir"] / "df_with_response_and_topics.csv",
        ["Title", "URL", "AlertFlag", "topic", "RelevantKeywords"],
    )

    assert len(news_rows) > 0
    assert len(llm_rows) > 0
    assert len(topic_rows) > 0
