from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import time as perf_time
from typing import List

from config.settings import get_config
from models.errors import ValidationError
from services.pipeline import (
    cleanup_old_data,
    export_dashboard,
    extract_news_info,
    fetch_news,
    generate_report,
    run_topic_modeling,
    save_news,
)
from services.seca_timeline import run_seca_light_timeline
from services.storage import data_path, read_csv
from utils.logging import get_logger, log_context
from utils.rows import llm_rows_from_records, news_rows_from_records

logger = get_logger(__name__)


def _parse_anchor_date(anchor_date: str | None) -> date:
    if not anchor_date:
        return datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(anchor_date)
    except ValueError as exc:
        raise ValidationError("anchor_date must use YYYY-MM-DD format") from exc


def _build_day_anchors(days: int, anchor: date, hour: int = 7, minute: int = 0) -> List[datetime]:
    if days <= 0:
        raise ValidationError("days must be greater than zero")
    anchors: List[datetime] = []
    start_day = anchor - timedelta(days=days - 1)
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        anchors.append(datetime.combine(day, time(hour=hour, minute=minute, tzinfo=timezone.utc)))
    return anchors


def run_replay_days(
    *,
    days: int = 7,
    hours: int = 24,
    include_trending: bool = True,
    anchor_date: str | None = None,
    run_seca: bool = True,
    run_cleanup: bool = True,
) -> None:
    if hours <= 0:
        raise ValidationError("hours must be greater than zero")

    cfg = get_config()
    anchor = _parse_anchor_date(anchor_date)
    anchors = _build_day_anchors(days, anchor)
    replay_anchor = anchor.isoformat()

    logger.warning(
        "replay_week_writes_live_results",
        extra={
            "event": "replay_week_writes_live_results",
            "component": "services.replay",
            "operation": "run_replay_days",
            "status": "warning",
        },
    )

    for idx, anchor_dt in enumerate(anchors, start=1):
        started = perf_time.perf_counter()
        replay_day = anchor_dt.date().isoformat()
        context = {
            "replay_mode": True,
            "replay_day": replay_day,
            "replay_index": idx,
            "replay_total_days": len(anchors),
            "replay_anchor_date": replay_anchor,
        }
        with log_context(**context):
            logger.info(
                "pipeline_run_start",
                extra={
                    "event": "pipeline_run_start",
                    "component": "services.replay",
                    "operation": "run_replay_days",
                    "stage": "full",
                    "stage_status": "started",
                },
            )
            try:
                rows = fetch_news(
                    hours=hours,
                    include_trending=include_trending,
                    reference_now_utc=anchor_dt,
                )
                save_news(rows)
                news_rows = news_rows_from_records(read_csv(data_path("news_data.csv")))
                extract_news_info(news_rows)
                llm_rows = llm_rows_from_records(read_csv(data_path("news_data_with_llm_info.csv")))
                run_topic_modeling(llm_rows)
                report_rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
                generate_report(report_rows)
                export_dashboard()
                if run_seca:
                    try:
                        run_seca_light_timeline()
                    except Exception:
                        logger.exception(
                            "seca_light_non_blocking_error",
                            extra={
                                "event": "seca_light_non_blocking_error",
                                "component": "services.replay",
                                "operation": "run_replay_days",
                                "stage": "seca_light",
                                "stage_status": "failed",
                                "skip_reason": "unexpected_exception",
                            },
                        )
                if run_cleanup:
                    cleanup_old_data(cfg.cleanup_days_to_keep, reference_now_utc=anchor_dt)
                logger.info(
                    "pipeline_run_end",
                    extra={
                        "event": "pipeline_run_end",
                        "component": "services.replay",
                        "operation": "run_replay_days",
                        "run_status": "succeeded",
                        "duration_ms": int((perf_time.perf_counter() - started) * 1000),
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
                        "component": "services.replay",
                        "operation": "run_replay_days",
                        "run_status": "failed",
                        "duration_ms": int((perf_time.perf_counter() - started) * 1000),
                        "stages_succeeded": 0,
                        "stages_failed": 1,
                        "stages_skipped": 0,
                    },
                )
                raise
