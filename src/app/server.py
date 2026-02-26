from __future__ import annotations

import time
import uuid

from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import get_config
from models.errors import AppError, from_exception
from services.pipeline import (
    cleanup_old_data,
    extract_news_info,
    export_dashboard,
    fetch_news,
    generate_report,
    run_topic_modeling,
    save_news,
)
from services.storage import data_path, read_csv
from utils.logging import configure_logging, get_logger, log_context, set_correlation_id, set_run_id
from utils.rows import llm_rows_from_records, news_rows_from_records

logger = get_logger(__name__)


def create_app() -> Flask:
    configure_logging()
    app = Flask(__name__)

    @app.before_request
    def _before_request():
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
        run_id = request.headers.get("X-Run-Id", str(uuid.uuid4()))
        request.environ["risklive.correlation_id"] = correlation_id
        request.environ["risklive.run_id"] = run_id
        request.environ["risklive.started_at"] = time.perf_counter()
        set_correlation_id(correlation_id)
        set_run_id(run_id)

    @app.after_request
    def _after_request(response):
        correlation_id = request.environ.get("risklive.correlation_id", "-")
        run_id = request.environ.get("risklive.run_id", "-")
        started_at = request.environ.get("risklive.started_at")
        duration_ms = int((time.perf_counter() - started_at) * 1000) if started_at else None
        response.headers["X-Correlation-Id"] = correlation_id
        response.headers["X-Run-Id"] = run_id
        logger.info(
            "request_complete",
            extra={
                "event": "request_complete",
                "route": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "operation": request.endpoint or "-",
                "component": "app.server",
            },
        )
        return response

    @app.errorhandler(AppError)
    def _handle_app_error(error: AppError):
        correlation_id = request.environ.get("risklive.correlation_id", "-")
        logger.error(
            "app_error",
            extra={
                "event": "app_error",
                "route": request.path,
                "status": error.http_status,
                "error_code": error.code,
                "retryable": error.retryable,
                "operation": request.endpoint or "-",
                "component": "app.server",
            },
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "retryable": error.retryable,
                        "correlation_id": correlation_id,
                    },
                }
            ),
            error.http_status,
        )

    @app.errorhandler(Exception)
    def _handle_unexpected(error: Exception):
        app_error = from_exception(error, "Unexpected server error")
        correlation_id = request.environ.get("risklive.correlation_id", "-")
        logger.exception(
            "unexpected_error",
            extra={
                "event": "unexpected_error",
                "route": request.path,
                "status": 500,
                "error_code": app_error.code,
                "retryable": app_error.retryable,
                "operation": request.endpoint or "-",
                "component": "app.server",
            },
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": app_error.code,
                        "message": "Unexpected server error",
                        "retryable": app_error.retryable,
                        "correlation_id": correlation_id,
                    },
                }
            ),
            500,
        )

    @app.route("/")
    def home():
        return jsonify({"status": "ok"})

    @app.route("/trigger/regular")
    def trigger_regular():
        hours = request.args.get("hours", default=1, type=int)
        with log_context(component="app.server", operation="trigger_regular"):
            rows = fetch_news(hours=hours, include_trending=False)
            save_news(rows)
        return jsonify({"status": "triggered", "hours": hours})

    @app.route("/trigger/trending")
    def trigger_trending():
        with log_context(component="app.server", operation="trigger_trending"):
            rows = fetch_news(hours=24, include_trending=True)
            save_news(rows)
        return jsonify({"status": "triggered", "trending": True})

    @app.route("/trigger/extract")
    def trigger_extract():
        with log_context(component="app.server", operation="trigger_extract"):
            rows = news_rows_from_records(read_csv(data_path("news_data.csv")))
            extract_news_info(rows)
        return jsonify({"status": "triggered", "task": "extract"})

    @app.route("/trigger/topic")
    def trigger_topic():
        with log_context(component="app.server", operation="trigger_topic"):
            rows = llm_rows_from_records(read_csv(data_path("news_data_with_llm_info.csv")))
            run_topic_modeling(rows)
        return jsonify({"status": "triggered", "task": "topic"})

    @app.route("/trigger/report")
    def trigger_report():
        with log_context(component="app.server", operation="trigger_report"):
            rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
            generate_report(rows)
        return jsonify({"status": "triggered", "task": "report"})

    @app.route("/trigger/dashboard")
    def trigger_dashboard():
        with log_context(component="app.server", operation="trigger_dashboard"):
            export_dashboard()
        return jsonify({"status": "triggered", "task": "dashboard"})

    @app.route("/trigger/full")
    def trigger_full():
        hours = request.args.get("hours", default=24, type=int)
        include_trending = request.args.get("trending", default=1, type=int) == 1
        with log_context(component="app.server", operation="trigger_full"):
            manual_fetch_and_process(hours=hours, include_trending=include_trending)
        return jsonify({"status": "triggered", "task": "full", "hours": hours, "trending": include_trending})

    @app.route("/trigger/cleanup")
    def trigger_cleanup():
        cfg = get_config()
        with log_context(component="app.server", operation="trigger_cleanup"):
            removed = cleanup_old_data(cfg.cleanup_days_to_keep)
        return jsonify({"status": "triggered", "removed": removed})

    return app


def start_scheduler(app: Flask) -> BackgroundScheduler:
    cfg = get_config()
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: _run_job("fetch_and_process", lambda: fetch_and_process(app)), "cron", hour=7)
    scheduler.add_job(
        lambda: _run_job(
            "cleanup_old_data",
            lambda: cleanup_old_data(cfg.cleanup_days_to_keep),
        ),
        "cron",
        hour=6,
        minute=30,
    )
    scheduler.start()
    return scheduler

def _run_job(name: str, fn) -> None:
    correlation_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)
    set_run_id(run_id)
    started = time.perf_counter()
    with log_context(component="scheduler", operation=name, job=name):
        logger.info("job_start", extra={"event": "job_start", "job": name})
        try:
            fn()
        except Exception:
            logger.exception(
                "job_failed",
                extra={"event": "job_failed", "job": name, "duration_ms": int((time.perf_counter() - started) * 1000)},
            )
            raise
        logger.info(
            "job_complete",
            extra={"event": "job_complete", "job": name, "duration_ms": int((time.perf_counter() - started) * 1000)},
        )


def fetch_and_process(_app: Flask) -> None:
    manual_fetch_and_process(hours=24, include_trending=True)
    export_dashboard()


def manual_fetch_and_process(hours: int = 24, include_trending: bool = True) -> None:
    started = time.perf_counter()
    logger.info(
        "pipeline_run_start",
        extra={
            "event": "pipeline_run_start",
            "component": "app.server",
            "operation": "manual_fetch_and_process",
            "stage": "full",
            "stage_status": "started",
        },
    )
    try:
        rows = fetch_news(hours=hours, include_trending=include_trending)
        save_news(rows)
        rows = news_rows_from_records(read_csv(data_path("news_data.csv")))
        extract_news_info(rows)
        rows = llm_rows_from_records(read_csv(data_path("news_data_with_llm_info.csv")))
        run_topic_modeling(rows)
        rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
        generate_report(rows)
        logger.info(
            "pipeline_run_end",
            extra={
                "event": "pipeline_run_end",
                "component": "app.server",
                "operation": "manual_fetch_and_process",
                "run_status": "succeeded",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "stages_succeeded": 1,
                "stages_failed": 0,
                "stages_skipped": 0,
            },
        )
    except Exception:
        logger.exception(
            "pipeline_run_end",
            extra={
                "event": "pipeline_run_end",
                "component": "app.server",
                "operation": "manual_fetch_and_process",
                "run_status": "failed",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "stages_succeeded": 0,
                "stages_failed": 1,
                "stages_skipped": 0,
            },
        )
        raise


def main() -> None:
    configure_logging()
    app = create_app()
    start_scheduler(app)
    app.run(host="0.0.0.0", port=5001)


if __name__ == "__main__":  # pragma: no cover
    main()
