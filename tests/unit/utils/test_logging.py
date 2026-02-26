from __future__ import annotations

import json
import logging

from utils.logging import get_logger
from utils.logging import JsonFormatter, log_context, pipeline_stage, set_correlation_id, set_run_id


def test_get_logger():
    logger = get_logger("name")
    assert logger.name == "name"


def test_json_formatter_redacts_sensitive_fields():
    set_correlation_id("cid-1")
    set_run_id("rid-1")
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="risklive.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.event = "unit_test"
    record.component = "tests"
    record.operation = "format"
    record.api_key = "super-secret"
    payload = json.loads(formatter.format(record))
    assert payload["correlation_id"] == "cid-1"
    assert payload["run_id"] == "rid-1"
    assert payload["message"] == "hello"
    assert "api_key" not in payload


def test_pipeline_stage_emits_start_end(caplog):
    logger = get_logger("tests.pipeline_stage")
    with caplog.at_level(logging.INFO):
        with pipeline_stage(
            logger,
            stage="fetch",
            component="tests",
            operation="unit",
            input_rows=3,
        ) as end_stage:
            end_stage("succeeded", output_rows=2)

    events = [getattr(record, "event", "") for record in caplog.records]
    assert "pipeline_stage_start" in events
    assert "pipeline_stage_end" in events


def test_pipeline_stage_auto_end_and_idempotent_end(caplog):
    logger = get_logger("tests.pipeline_stage.auto")
    with caplog.at_level(logging.INFO):
        with pipeline_stage(
            logger,
            stage="extract",
            component="tests",
            operation="auto",
        ) as end_stage:
            end_stage("succeeded", output_rows=1)
            end_stage("succeeded", output_rows=2)  # no-op branch

        with pipeline_stage(
            logger,
            stage="report",
            component="tests",
            operation="auto2",
        ):
            pass

    end_events = [r for r in caplog.records if getattr(r, "event", "") == "pipeline_stage_end"]
    assert len(end_events) >= 2


def test_log_context_does_not_override_explicit_component_operation():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="services.pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="stage done",
        args=(),
        exc_info=None,
    )
    record.event = "pipeline_stage_end"
    record.component = "services.pipeline"
    record.operation = "extract_news_info"
    record.stage = "extract"

    with log_context(component="app.cli", operation="full", command="full"):
        payload = json.loads(formatter.format(record))

    assert payload["component"] == "services.pipeline"
    assert payload["operation"] == "extract_news_info"
    assert payload["command"] == "full"
