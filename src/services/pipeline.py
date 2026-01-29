from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from config.settings import get_config
from models.csv import LLMEnrichedRow, NewsRow
from services.ingestion import collect_news
from services.extraction import extract_from_rows
from services.reporting import generate_reports_from_rows
from services.storage import data_path, load_if_exists, write_csv
from services.topic_modeling import compute_topic_modeling, compute_topic_visualizations
from utils.rows import (
    llm_rows_from_records,
    news_rows_from_records,
    records_from_llm_rows,
    records_from_news_rows,
)


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


def fetch_news(hours: int = 1, include_trending: bool = False) -> List[NewsRow]:
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
    return rows


def save_news(rows: List[NewsRow], filename: str = "news_data.csv") -> List[NewsRow]:
    path = data_path(filename)
    existing = load_if_exists(path)
    existing_rows = news_rows_from_records(existing) if existing else []
    merged = _dedupe_rows(existing_rows + rows, lambda r: _url_key(r.url))
    write_csv(records_from_news_rows(merged), path)
    return merged


def extract_news_info(rows: List[NewsRow], filename: str = "news_data_with_llm_info.csv") -> List[LLMEnrichedRow]:
    path = data_path(filename)
    existing = load_if_exists(path)
    existing_rows = llm_rows_from_records(existing) if existing else []
    existing_urls = {_url_key(row.url) for row in existing_rows}
    todo = [row for row in rows if _url_key(row.url) not in existing_urls]
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
    write_csv(records_from_llm_rows(merged), path)
    return merged


def run_topic_modeling(rows: List[LLMEnrichedRow]):
    return compute_topic_modeling(rows)


def run_topic_visualizations():
    return compute_topic_visualizations()


def generate_report(rows: List[LLMEnrichedRow], filename: str = "df_report.csv") -> List[dict]:
    if not rows or rows[0].topic is None:
        raise ValueError("topic column is required for report generation")

    reports = []
    grouped: dict[int, List[LLMEnrichedRow]] = {}
    for row in rows:
        if row.alert_flag != "Red":
            continue
        if row.topic is None:
            continue
        grouped.setdefault(int(row.topic), []).append(row)

    for topic, group in grouped.items():
        report = generate_reports_from_rows(group)[0]
        reports.append(
            {
                "topic": topic,
                "keyword": report.keyword,
                "input_prompt": report.input_prompt,
                "response": report.response,
            }
        )

    write_csv(reports, data_path(filename))
    return reports


def cleanup_old_data(days_to_keep: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    path = data_path("news_data_with_llm_info.csv")
    records = load_if_exists(path)
    if not records:
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
    return before - len(kept)
