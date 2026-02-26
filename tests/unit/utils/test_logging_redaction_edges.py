from __future__ import annotations

from pathlib import Path

from utils import logging as logging_service


def test_logging_redaction_remaining_branches():
    assert logging_service._redact_text("Bearer abc") == "***REDACTED***"
    payload = logging_service._redact_dict({"token": "x", "nested": {"secret": "y"}})
    assert payload["token"] == "***REDACTED***"
    assert payload["nested"]["secret"] == "***REDACTED***"


def test_log_artifact_written_handles_missing_path(caplog):
    logger = logging_service.get_logger("tests.artifact")
    with caplog.at_level("INFO"):
        logging_service.log_artifact_written(
            logger,
            stage="report",
            operation="unit",
            component="tests",
            artifact_path=Path("/definitely/missing/file.csv"),
            artifact_type="csv",
            artifact_rows=0,
        )
    records = [r for r in caplog.records if getattr(r, "event", "") == "artifact_written"]
    assert records
