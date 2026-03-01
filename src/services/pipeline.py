from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List

from config import settings as settings_module
from config.settings import get_config
from models.csv import LLMEnrichedRow, NewsRow
from models.errors import ValidationError
from services.ingestion import collect_news
from services.extraction import extract_from_rows
from services.reporting import generate_reports_from_rows
from services.storage import backup_path, data_path, get_data_dir, load_if_exists, write_csv
from services.topic_modeling import compute_topic_modeling, compute_topic_visualizations
from services.dashboard_export import main as export_dashboard_main
from utils.rows import (
    llm_rows_from_records,
    news_rows_from_records,
    records_from_llm_rows,
    records_from_news_rows,
)
from utils.logging import get_logger, log_artifact_written, pipeline_stage

logger = get_logger(__name__)


def _url_key(value) -> str:
    return str(value or "")


def _dedupe_rows(rows: Iterable, key_fn) -> List:
    seen = set()
    result = []
    for row in rows:
        key = key_fn(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _merge_rows_with_price(existing_rows: Iterable, incoming_rows: Iterable, key_fn) -> List:
    merged_by_key = {}
    ordered: List = []
    for row in list(existing_rows) + list(incoming_rows):
        key = key_fn(row)
        current = merged_by_key.get(key)
        if current is None:
            merged_by_key[key] = row
            ordered.append(row)
            continue
        current_price = getattr(current, "source_price", None)
        incoming_price = getattr(row, "source_price", None)
        if current_price is None and incoming_price is not None:
            setattr(current, "source_price", incoming_price)
    return ordered


def _fallback_report_keyword(rows: List[LLMEnrichedRow], topic: int) -> str:
    keyword_counter: Counter[str] = Counter()
    for row in rows:
        for keyword in row.relevant_keywords or []:
            normalized = str(keyword).strip()
            if normalized:
                keyword_counter[normalized] += 1
    if keyword_counter:
        return ", ".join([value for value, _ in keyword_counter.most_common(3)])

    for row in rows:
        summary = (row.short_summary or "").strip()
        if summary:
            return summary[:120]

    for row in rows:
        title = (row.title or "").strip()
        if title:
            return title[:120]

    return f"topic-{topic}"


def _parse_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_key(record: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in record.items()))


def _dedupe_record_rows(rows: list[dict]) -> list[dict]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    deduped: list[dict] = []
    for row in rows:
        key = _record_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def fetch_news(
    hours: int = 1,
    include_trending: bool = False,
    reference_now_utc: datetime | None = None,
) -> List[NewsRow]:
    with pipeline_stage(
        logger,
        stage="fetch",
        component="services.pipeline",
        operation="fetch_news",
        input_rows=0,
    ) as end_stage:
        cfg = get_config()
        queries = list(cfg.categories) + list(cfg.queries)
        if include_trending:
            queries += list(cfg.trending)
        articles = collect_news(
            queries=queries,
            hours=hours,
            reference_now_utc=reference_now_utc,
        )

        rows: List[NewsRow] = []
        for article in articles:
            rows.append(
                NewsRow(
                    Title=article.title,
                    URL=str(article.url) if article.url else "",
                    Description=article.description,
                    Timestamp=article.timestamp.isoformat()
                    if article.timestamp
                    else datetime.now(timezone.utc).isoformat(),
                    Query=article.query or "",
                    Source_Price=article.source_price,
                )
            )
        end_stage("succeeded", input_rows=len(queries), output_rows=len(rows))
        return rows


def save_news(rows: List[NewsRow], filename: str = "news_data.csv") -> List[NewsRow]:
    with pipeline_stage(
        logger,
        stage="save",
        component="services.pipeline",
        operation="save_news",
        input_rows=len(rows),
    ) as end_stage:
        path = data_path(filename)
        existing = load_if_exists(path)
        existing_rows = news_rows_from_records(existing) if existing else []
        merged = _merge_rows_with_price(existing_rows, rows, lambda r: _url_key(r.url))
        deduped_rows = max(0, (len(existing_rows) + len(rows)) - len(merged))
        write_csv(records_from_news_rows(merged), path)
        log_artifact_written(
            logger,
            stage="save",
            operation="save_news",
            component="services.pipeline",
            artifact_path=path,
            artifact_type="csv",
            artifact_rows=len(merged),
        )
        end_stage(
            "succeeded",
            output_rows=len(merged),
            deduped_rows=deduped_rows,
        )
        return merged


def extract_news_info(rows: List[NewsRow], filename: str = "news_data_with_llm_info.csv") -> List[LLMEnrichedRow]:
    with pipeline_stage(
        logger,
        stage="extract",
        component="services.pipeline",
        operation="extract_news_info",
        input_rows=len(rows),
    ) as end_stage:
        path = data_path(filename)
        existing = load_if_exists(path)
        existing_rows = llm_rows_from_records(existing) if existing else []
        incoming_price_by_url = {
            _url_key(row.url): row.source_price
            for row in rows
            if row.source_price is not None
        }
        for row in existing_rows:
            key = _url_key(row.url)
            if row.source_price is None and key in incoming_price_by_url:
                row.source_price = incoming_price_by_url[key]
        existing_urls = {_url_key(row.url) for row in existing_rows}
        todo = [row for row in rows if _url_key(row.url) not in existing_urls]
        if not todo:
            end_stage(
                "skipped",
                output_rows=len(existing_rows),
                deduped_rows=len(rows),
                skip_reason="no_input_rows",
            )
            return existing_rows

        records = extract_from_rows(todo)
        enriched_rows: List[LLMEnrichedRow] = []
        for idx, record in enumerate(records):
            base = todo[idx]
            result = record.result
            metrics = getattr(record, "metrics", None)
            enriched = LLMEnrichedRow(
                Title=base.title,
                URL=str(base.url) if base.url else "",
                Description=base.description,
                Timestamp=base.timestamp.isoformat() if base.timestamp else None,
                Query=base.query or "",
                Source_Price=base.source_price,
                LLM_Response=result.model_dump() if result else None,
                LLM_Price=metrics.price_usd if metrics else None,
                LLM_Token_Usage=metrics.token_usage.model_dump() if metrics and metrics.token_usage else None,
                PromptTokens=metrics.token_usage.prompt_tokens
                if metrics and metrics.token_usage
                else None,
                CompletionTokens=metrics.token_usage.completion_tokens
                if metrics and metrics.token_usage
                else None,
                TotalTokens=metrics.token_usage.total_tokens
                if metrics and metrics.token_usage
                else None,
                RelevantKeywords=result.relevant_keywords if result else [],
                ShortSummary=result.short_summary if result else "",
                Relevance=result.relevance.value if result else "",
                RelevanceReason=result.relevance_reason if result else "",
                AlertFlag=result.alert_flag.value if result else "",
                AlertReason=result.alert_reason if result else "",
                NewsCategory=result.news_category if result else "",
                API_Timestamp=datetime.now(timezone.utc).isoformat(),
            )
            enriched_rows.append(enriched)

        merged = _merge_rows_with_price(existing_rows, enriched_rows, lambda r: _url_key(r.url))
        deduped_rows = max(0, (len(existing_rows) + len(enriched_rows)) - len(merged))
        write_csv(records_from_llm_rows(merged), path)
        log_artifact_written(
            logger,
            stage="extract",
            operation="extract_news_info",
            component="services.pipeline",
            artifact_path=path,
            artifact_type="csv",
            artifact_rows=len(merged),
        )
        end_stage(
            "succeeded",
            input_rows=len(todo),
            output_rows=len(merged),
            deduped_rows=deduped_rows,
        )
        return merged


def run_topic_modeling(rows: List[LLMEnrichedRow]):
    with pipeline_stage(
        logger,
        stage="topic",
        component="services.pipeline",
        operation="run_topic_modeling",
        input_rows=len(rows),
    ) as end_stage:
        artifacts = compute_topic_modeling(rows)
        if artifacts:
            data_csv = getattr(artifacts, "data_csv", None)
            model_dir = getattr(artifacts, "model_dir", None)
            if data_csv:
                log_artifact_written(
                    logger,
                    stage="topic",
                    operation="run_topic_modeling",
                    component="services.pipeline",
                    artifact_path=Path(data_csv),
                    artifact_type="csv",
                    artifact_rows=len(rows),
                )
            if model_dir:
                log_artifact_written(
                    logger,
                    stage="topic",
                    operation="run_topic_modeling",
                    component="services.pipeline",
                    artifact_path=Path(model_dir),
                    artifact_type="model",
                    artifact_rows=None,
                )
        end_stage(
            "succeeded",
            output_rows=len(getattr(artifacts, "assignments", []) or []),
        )
        return artifacts


def run_topic_visualizations():
    with pipeline_stage(
        logger,
        stage="topic",
        component="services.pipeline",
        operation="run_topic_visualizations",
    ) as end_stage:
        output = compute_topic_visualizations()
        end_stage("succeeded")
        return output


def generate_report(rows: List[LLMEnrichedRow], filename: str = "df_report.csv") -> List[dict]:
    with pipeline_stage(
        logger,
        stage="report",
        component="services.pipeline",
        operation="generate_report",
        input_rows=len(rows),
    ) as end_stage:
        if not rows or rows[0].topic is None:
            raise ValidationError("topic column is required for report generation")

        reports = []
        grouped: dict[int, List[LLMEnrichedRow]] = {}
        for row in rows:
            if row.alert_flag != "Red":
                continue
            if row.topic is None:
                continue
            grouped.setdefault(int(row.topic), []).append(row)

        if not grouped:
            path = data_path(filename)
            write_csv([], path)
            log_artifact_written(
                logger,
                stage="report",
                operation="generate_report",
                component="services.pipeline",
                artifact_path=path,
                artifact_type="csv",
                artifact_rows=0,
            )
            end_stage("skipped", output_rows=0, skip_reason="no_reportable_red_topics")
            return reports

        for topic, group in grouped.items():
            report = generate_reports_from_rows(group)[0]
            keyword = (report.keyword or "").strip() or _fallback_report_keyword(group, topic)
            reports.append(
                {
                    "topic": topic,
                    "keyword": keyword,
                    "input_prompt": report.input_prompt,
                    "response": report.response,
                }
            )

        path = data_path(filename)
        write_csv(reports, path)
        log_artifact_written(
            logger,
            stage="report",
            operation="generate_report",
            component="services.pipeline",
            artifact_path=path,
            artifact_type="csv",
            artifact_rows=len(reports),
        )
        end_stage("succeeded", output_rows=len(reports))
        return reports


def cleanup_old_data(days_to_keep: int, reference_now_utc: datetime | None = None) -> int:
    with pipeline_stage(
        logger,
        stage="cleanup",
        component="services.pipeline",
        operation="cleanup_old_data",
    ) as end_stage:
        effective_now = (reference_now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
        retention_basis = "replay_anchor" if reference_now_utc else "runtime_now"
        cutoff = effective_now - timedelta(days=days_to_keep)
        data_dir = get_data_dir()
        if not data_dir.exists():
            end_stage("skipped", input_rows=0, output_rows=0, skip_reason="data_dir_missing")
            return 0

        total_input_rows = 0
        total_output_rows = 0
        total_removed_rows = 0
        processed_files = 0

        for path in sorted(data_dir.glob("*.csv")):
            if path.name == "df_report.csv":
                continue

            records = load_if_exists(path)
            if not records:
                continue
            if "Timestamp" not in records[0]:
                logger.warning(
                    "cleanup_missing_timestamp_column",
                    extra={
                        "event": "cleanup_missing_timestamp_column",
                        "component": "services.pipeline",
                        "operation": "cleanup_old_data",
                        "stage": "cleanup",
                        "status": "warning",
                        "cleanup_filename": path.name,
                    },
                )
                continue

            processed_files += 1
            before = len(records)
            invalid_ts_rows = 0
            kept: list[dict] = []
            to_backup: list[dict] = []
            for record in records:
                ts = _parse_timestamp(record.get("Timestamp"))
                if ts is None:
                    invalid_ts_rows += 1
                    continue
                if ts >= cutoff:
                    kept.append(record)
                else:
                    to_backup.append(record)

            write_csv(kept, path)
            log_artifact_written(
                logger,
                stage="cleanup",
                operation="cleanup_old_data",
                component="services.pipeline",
                artifact_path=path,
                artifact_type="csv",
                artifact_rows=len(kept),
            )

            if to_backup:
                backup_file = backup_path(path.name)
                existing_backup = load_if_exists(backup_file) or []
                merged_backup = _dedupe_record_rows([*existing_backup, *to_backup])
                write_csv(merged_backup, backup_file)
                log_artifact_written(
                    logger,
                    stage="cleanup",
                    operation="cleanup_old_data",
                    component="services.pipeline",
                    artifact_path=backup_file,
                    artifact_type="csv",
                    artifact_rows=len(merged_backup),
                )

            removed = len(to_backup) + invalid_ts_rows
            if invalid_ts_rows > 0:
                logger.warning(
                    "cleanup_invalid_timestamps_dropped",
                    extra={
                        "event": "cleanup_invalid_timestamps_dropped",
                        "component": "services.pipeline",
                        "operation": "cleanup_old_data",
                        "stage": "cleanup",
                        "status": "warning",
                        "cleanup_filename": path.name,
                        "dropped_invalid_timestamp_rows": invalid_ts_rows,
                    },
                )
            total_input_rows += before
            total_output_rows += len(kept)
            total_removed_rows += removed
            logger.info(
                "cleanup_file_summary",
                extra={
                    "event": "cleanup_file_summary",
                    "component": "services.pipeline",
                    "operation": "cleanup_old_data",
                    "stage": "cleanup",
                    "status": "ok",
                    "cleanup_filename": path.name,
                    "input_rows": before,
                    "output_rows": len(kept),
                    "archived_rows": len(to_backup),
                    "dropped_invalid_timestamp_rows": invalid_ts_rows,
                    "cutoff_iso": cutoff.isoformat(),
                    "retention_basis": retention_basis,
                },
            )

        if processed_files == 0:
            end_stage("skipped", input_rows=0, output_rows=0, skip_reason="no_input_rows")
            return 0
        end_stage(
            "succeeded",
            input_rows=total_input_rows,
            output_rows=total_output_rows,
            deduped_rows=total_removed_rows,
        )
        return total_removed_rows


def export_dashboard() -> None:
    with pipeline_stage(
        logger,
        stage="dashboard_export",
        component="services.pipeline",
        operation="export_dashboard",
    ) as end_stage:
        export_dashboard_main()
        dashboard_path = settings_module.ROOT_DIR / "results" / "web" / "dashboard.json"
        if dashboard_path.exists():
            log_artifact_written(
                logger,
                stage="dashboard_export",
                operation="export_dashboard",
                component="services.pipeline",
                artifact_path=dashboard_path,
                artifact_type="json",
            )
        end_stage("succeeded")
