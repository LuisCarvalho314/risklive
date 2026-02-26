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
from services.storage import data_path, load_if_exists, write_csv
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


def fetch_news(hours: int = 1, include_trending: bool = False) -> List[NewsRow]:
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
        articles = collect_news(queries=queries, hours=hours)

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
        merged = _dedupe_rows(existing_rows + rows, lambda r: _url_key(r.url))
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

        merged = _dedupe_rows(existing_rows + enriched_rows, lambda r: _url_key(r.url))
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


def cleanup_old_data(days_to_keep: int) -> int:
    with pipeline_stage(
        logger,
        stage="cleanup",
        component="services.pipeline",
        operation="cleanup_old_data",
    ) as end_stage:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        path = data_path("news_data_with_llm_info.csv")
        records = load_if_exists(path)
        if not records:
            end_stage("skipped", input_rows=0, output_rows=0, skip_reason="no_input_rows")
            return 0
        rows = llm_rows_from_records(records)
        before = len(rows)
        kept = []
        for row in rows:
            if row.timestamp is None:
                continue
            ts = row.timestamp if isinstance(row.timestamp, datetime) else None
            if ts is None:
                continue
            if ts >= cutoff:
                kept.append(row)
        write_csv(records_from_llm_rows(kept), path)
        removed = before - len(kept)
        log_artifact_written(
            logger,
            stage="cleanup",
            operation="cleanup_old_data",
            component="services.pipeline",
            artifact_path=path,
            artifact_type="csv",
            artifact_rows=len(kept),
        )
        end_stage("succeeded", input_rows=before, output_rows=len(kept), deduped_rows=removed)
        return removed


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
