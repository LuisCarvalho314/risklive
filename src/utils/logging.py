from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any


def get_project_root() -> Path:
    # If this file is src/utils/logging.py, then:
    # __file__ -> .../risklive/src/utils/logging.py
    # parents[2] -> .../risklive
    return Path(__file__).resolve().parents[2]


_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")
_run_id: ContextVar[str] = ContextVar("run_id", default="-")
_log_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})
_SENSITIVE_KEYS = {"api_key", "authorization", "token", "secret", "prompt", "text", "content"}


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in list(record.__dict__.items()):
            lowered = str(key).lower()
            if lowered in _SENSITIVE_KEYS or any(s in lowered for s in _SENSITIVE_KEYS):
                record.__dict__[key] = "***REDACTED***"
                continue
            if isinstance(value, str):
                record.__dict__[key] = _redact_text(value)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.funcName),
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
            "run_id": get_run_id(),
            "component": getattr(record, "component", "-"),
            "operation": getattr(record, "operation", "-"),
        }
        for key in (
            "route",
            "command",
            "job",
            "status",
            "duration_ms",
            "error_code",
            "retryable",
            "stage",
            "stage_status",
            "run_status",
            "input_rows",
            "output_rows",
            "deduped_rows",
            "artifact_type",
            "artifact_path",
            "artifact_rows",
            "artifact_bytes",
            "skip_reason",
            "stages_succeeded",
            "stages_failed",
            "stages_skipped",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        context = get_log_context()
        if context:
            for key, value in context.items():
                current = payload.get(key)
                if current in (None, "-", ""):
                    payload[key] = value
        return json.dumps(_redact_dict(payload), default=str)


def _redact_text(value: str) -> str:
    lowered = value.lower()
    if any(token in lowered for token in ("api_key", "authorization", "bearer ", "secret")):
        return "***REDACTED***"
    return value


def _redact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if lowered in _SENSITIVE_KEYS or any(s in lowered for s in _SENSITIVE_KEYS):
            out[key] = "***REDACTED***"
        elif isinstance(value, dict):
            out[key] = _redact_dict(value)
        elif isinstance(value, str):
            out[key] = _redact_text(value)
        else:
            out[key] = value
    return out


def configure_logging(project_root: Path | None = None) -> None:
    """
    Configure logging to both console and logs/app.log.
    Call once at process startup (e.g., in cli.py main()).
    """
    root = project_root or get_project_root()

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = (logs_dir / "app.log").resolve()

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if configure_logging() is called more than once
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            existing_path = Path(getattr(handler, "baseFilename", "")).resolve()
            if existing_path == log_file_path:
                return

    formatter = JsonFormatter()
    redaction_filter = RedactionFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction_filter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value or "-")


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_run_id(value: str) -> None:
    _run_id.set(value or "-")


def get_run_id() -> str:
    return _run_id.get()


def get_log_context() -> dict[str, Any]:
    return dict(_log_context.get())


@contextmanager
def log_context(**kwargs: Any):
    current = dict(_log_context.get())
    current.update(kwargs)
    token = _log_context.set(current)
    try:
        yield
    finally:
        _log_context.reset(token)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def pipeline_stage(logger: logging.Logger, *, stage: str, component: str, operation: str, **base: Any):
    started_at = time.perf_counter()
    finished = False

    logger.info(
        "pipeline_stage_start",
        extra={
            "event": "pipeline_stage_start",
            "component": component,
            "operation": operation,
            "stage": stage,
            "stage_status": "started",
            **base,
        },
    )

    def end(stage_status: str, **fields: Any) -> None:
        nonlocal finished
        if finished:
            return
        finished = True
        logger.info(
            "pipeline_stage_end",
            extra={
                "event": "pipeline_stage_end",
                "component": component,
                "operation": operation,
                "stage": stage,
                "stage_status": stage_status,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                **base,
                **fields,
            },
        )

    try:
        yield end
    except Exception as exc:
        end(
            "failed",
            error_code=getattr(exc, "code", exc.__class__.__name__),
            retryable=bool(getattr(exc, "retryable", False)),
        )
        raise
    else:
        if not finished:
            end("succeeded")


def log_artifact_written(
    logger: logging.Logger,
    *,
    stage: str,
    operation: str,
    component: str,
    artifact_path: Path | str,
    artifact_type: str,
    artifact_rows: int | None = None,
) -> None:
    resolved_path = Path(artifact_path)
    artifact_bytes = None
    try:
        artifact_bytes = resolved_path.stat().st_size
    except OSError:
        artifact_bytes = None

    logger.info(
        "artifact_written",
        extra={
            "event": "artifact_written",
            "component": component,
            "operation": operation,
            "stage": stage,
            "artifact_type": artifact_type,
            "artifact_path": str(resolved_path),
            "artifact_rows": artifact_rows,
            "artifact_bytes": artifact_bytes,
        },
    )
