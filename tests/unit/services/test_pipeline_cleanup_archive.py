from __future__ import annotations

from datetime import datetime, timezone

from services import pipeline as pipeline_service


def _reset_root(monkeypatch, tmp_path):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None


def test_cleanup_archives_timestamped_csvs(monkeypatch, tmp_path):
    from services.storage import backup_path, data_path, read_csv, write_csv

    _reset_root(monkeypatch, tmp_path)

    write_csv(
        [
            {"Title": "old-a", "Timestamp": "2026-02-01T00:00:00Z"},
            {"Title": "new-a", "Timestamp": "2026-02-27T00:00:00Z"},
        ],
        data_path("a.csv"),
    )
    write_csv(
        [
            {"Title": "old-b", "Timestamp": "2026-01-20T00:00:00Z"},
        ],
        data_path("b.csv"),
    )
    write_csv([{"Title": "x", "Value": "1"}], data_path("no_timestamp.csv"))
    write_csv([{"topic": 1, "response": "skip"}], data_path("df_report.csv"))

    removed = pipeline_service.cleanup_old_data(
        days_to_keep=3,
        reference_now_utc=datetime(2026, 2, 27, 0, 0, tzinfo=timezone.utc),
    )

    assert removed == 2
    assert [row["Title"] for row in read_csv(data_path("a.csv"))] == ["new-a"]
    assert read_csv(data_path("b.csv")) == []
    assert [row["Title"] for row in read_csv(backup_path("a.csv"))] == ["old-a"]
    assert [row["Title"] for row in read_csv(backup_path("b.csv"))] == ["old-b"]
    assert not backup_path("no_timestamp.csv").exists()


def test_cleanup_backup_dedupes_exact_rows(monkeypatch, tmp_path):
    from services.storage import backup_path, data_path, read_csv, write_csv

    _reset_root(monkeypatch, tmp_path)

    archived_row = {"Title": "dup", "Timestamp": "2026-01-01T00:00:00Z", "URL": "https://example.com/a"}
    write_csv([archived_row], backup_path("news_data.csv"))
    write_csv([archived_row], data_path("news_data.csv"))

    removed = pipeline_service.cleanup_old_data(
        days_to_keep=3,
        reference_now_utc=datetime(2026, 2, 27, 0, 0, tzinfo=timezone.utc),
    )

    assert removed == 1
    backup_rows = read_csv(backup_path("news_data.csv"))
    assert len(backup_rows) == 1
    assert backup_rows[0]["Title"] == "dup"


def test_cleanup_uses_reference_now_for_replay(monkeypatch, tmp_path):
    from services.storage import data_path, read_csv, write_csv

    _reset_root(monkeypatch, tmp_path)

    write_csv(
        [
            {"Title": "in-window-by-replay-anchor", "Timestamp": "2026-02-18T00:00:00Z"},
        ],
        data_path("news_data_with_llm_info.csv"),
    )

    removed = pipeline_service.cleanup_old_data(
        days_to_keep=3,
        reference_now_utc=datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc),
    )

    assert removed == 0
    assert len(read_csv(data_path("news_data_with_llm_info.csv"))) == 1
