from __future__ import annotations

import argparse
import sys
import time
import uuid

from models.errors import AppError, from_exception
from services.pipeline import (
    cleanup_old_data,
    extract_news_info,
    export_dashboard,
    fetch_news,
    generate_report,
    run_topic_modeling,
    run_topic_visualizations,
    save_news,
)
from services.storage import data_path, read_csv
from utils.rows import llm_rows_from_records, news_rows_from_records
from utils.logging import configure_logging, get_logger, log_context, set_correlation_id, set_run_id

logger = get_logger(__name__)


def main() -> None:
    configure_logging()
    correlation_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)
    set_run_id(run_id)
    parser = argparse.ArgumentParser(prog="risklive")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_cmd = sub.add_parser("fetch")
    fetch_cmd.add_argument("--hours", type=int, default=1)
    fetch_cmd.add_argument("--trending", action="store_true")

    sub.add_parser("extract")
    sub.add_parser("topic")
    sub.add_parser("visualize")
    sub.add_parser("report")
    sub.add_parser("dashboard")
    full_cmd = sub.add_parser("full")
    full_cmd.add_argument("--hours", type=int, default=24)
    full_cmd.add_argument("--trending", type=int, default=1)
    replay_cmd = sub.add_parser("replay-week")
    replay_cmd.add_argument("--days", type=int, default=7)
    replay_cmd.add_argument("--hours", type=int, default=24)
    replay_cmd.add_argument("--trending", type=int, default=1)
    replay_cmd.add_argument("--anchor-date", type=str, default=None)
    replay_cmd.add_argument("--run-seca", type=int, default=1)
    replay_cmd.add_argument("--run-cleanup", type=int, default=1)

    cleanup_cmd = sub.add_parser("cleanup")
    cleanup_cmd.add_argument("--days", type=int, default=3)

    args = parser.parse_args()

    started = time.perf_counter()
    logger.info(
        "pipeline_run_start",
        extra={
            "event": "pipeline_run_start",
            "component": "app.cli",
            "operation": args.command,
            "stage": args.command,
            "stage_status": "started",
        },
    )
    try:
        with log_context(component="app.cli", operation=args.command, command=args.command):
            if args.command == "fetch":
                rows = fetch_news(hours=args.hours, include_trending=args.trending)
                save_news(rows)
            elif args.command == "extract":
                rows = news_rows_from_records(read_csv(data_path("news_data.csv")))
                extract_news_info(rows)
            elif args.command == "topic":
                rows = llm_rows_from_records(read_csv(data_path("news_data_with_llm_info.csv")))
                run_topic_modeling(rows)
            elif args.command == "visualize":
                run_topic_visualizations()
            elif args.command == "report":
                rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
                generate_report(rows)
            elif args.command == "dashboard":
                export_dashboard()
            elif args.command == "cleanup":
                cleanup_old_data(args.days)
            elif args.command == "full":
                from app.server import manual_fetch_and_process

                manual_fetch_and_process(hours=args.hours, include_trending=args.trending == 1)
                export_dashboard()
            elif args.command == "replay-week":
                from services.replay import run_replay_days

                run_replay_days(
                    days=args.days,
                    hours=args.hours,
                    include_trending=args.trending == 1,
                    anchor_date=args.anchor_date,
                    run_seca=args.run_seca == 1,
                    run_cleanup=args.run_cleanup == 1,
                )
        logger.info(
            "pipeline_run_end",
            extra={
                "event": "pipeline_run_end",
                "component": "app.cli",
                "operation": args.command,
                "run_status": "succeeded",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "stages_succeeded": 1,
                "stages_failed": 0,
                "stages_skipped": 0,
            },
        )
    except AppError as exc:
        logger.error(
            "pipeline_run_end",
            extra={
                "event": "pipeline_run_end",
                "component": "app.cli",
                "operation": args.command,
                "run_status": "failed",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "stages_succeeded": 0,
                "stages_failed": 1,
                "stages_skipped": 0,
                "error_code": exc.code,
                "retryable": exc.retryable,
            },
        )
        logger.error(
            "cli_app_error",
            extra={
                "event": "cli_app_error",
                "component": "app.cli",
                "operation": args.command,
                "error_code": exc.code,
                "retryable": exc.retryable,
            },
        )
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        app_error = from_exception(exc, "Unexpected CLI failure")
        logger.error(
            "pipeline_run_end",
            extra={
                "event": "pipeline_run_end",
                "component": "app.cli",
                "operation": args.command,
                "run_status": "failed",
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "stages_succeeded": 0,
                "stages_failed": 1,
                "stages_skipped": 0,
                "error_code": app_error.code,
                "retryable": app_error.retryable,
            },
        )
        logger.exception(
            "cli_unexpected_error",
            extra={
                "event": "cli_unexpected_error",
                "component": "app.cli",
                "operation": args.command,
                "error_code": app_error.code,
            },
        )
        print(f"{app_error.code}: unexpected failure", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
