from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
from typing import Iterable, List

from valyu import Valyu

from config.settings import get_valyu_config
from models.errors import ConfigError, ExternalServiceError
from models.article import Article, ArticleSource

from utils.logging import get_logger

logger = get_logger(__name__)


def _extract_source_price(data: dict) -> float | None:
    for key in ("price", "result_price", "cost"):
        raw = data.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            return value
    return None


def _parse_publication_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)



def fetch_news(
    queries: Iterable[str],
    hours: int = 24,
    market: str = "GB",
    reference_now_utc: datetime | None = None,
) -> List[Article]:
    started = time.perf_counter()
    logger.info(
        "fetch_news_start",
        extra={
            "event": "fetch_news_start",
            "component": "adapters.valyu",
            "operation": "fetch_news",
            "stage": "fetch",
            "stage_status": "started",
        },
    )
    try:
        valyu_config = get_valyu_config()
    except Exception as exc:
        raise ConfigError("Unable to load Valyu configuration") from exc
    api_key = valyu_config.api_key.get_secret_value()

    if not api_key:
        raise ConfigError("VALYU_API_KEY is not set")

    try:
        client = Valyu(api_key)
    except Exception as exc:
        raise ExternalServiceError("Unable to initialize Valyu client", details={"exception": exc.__class__.__name__}) from exc
    effective_now = reference_now_utc or datetime.now(timezone.utc)
    end_date = effective_now.strftime("%Y-%m-%d")
    start_date = (effective_now - timedelta(hours=hours)).strftime("%Y-%m-%d")
    excluded_sources = valyu_config.runtime.excluded_sources
    max_num_results = valyu_config.runtime.max_num_results

    logger.debug(
        "Valyu params: start_date=%s end_date=%s max_num_results=%d excluded_sources=%s",
        start_date,
        end_date,
        max_num_results,
        excluded_sources,
    )

    articles: List[Article] = []
    total_priced_rows = 0
    total_price_usd = 0.0
    for query in queries:
        if not query:
            continue

        logger.debug("Valyu search query=%r", query)
        query_started = time.perf_counter()
        try:
            resp = client.search(
                query,
                search_type="news",
                start_date=start_date,
                end_date=end_date,
                max_num_results=max_num_results,
                url_only=True,
                response_length="short",
                country_code=market,
                excluded_sources=excluded_sources,
            )
        except Exception as exc:
            logger.error(
                "valyu_search_exception",
                extra={
                    "event": "valyu_search_exception",
                    "component": "adapters.valyu",
                    "operation": "fetch_news",
                    "stage": "fetch",
                    "stage_status": "failed",
                    "duration_ms": int((time.perf_counter() - query_started) * 1000),
                    "retryable": True,
                },
            )
            raise ExternalServiceError(
                "Valyu search request failed",
                details={"query": query, "exception": exc.__class__.__name__},
                retryable=True,
            ) from exc
        if not resp or not resp.success:
            logger.warning(
                "valyu_search_failed",
                extra={
                    "event": "valyu_search_failed",
                    "component": "adapters.valyu",
                    "operation": "fetch_news",
                    "stage": "fetch",
                    "status": "empty",
                    "duration_ms": int((time.perf_counter() - query_started) * 1000),
                },
            )
            # logger.warning("Valyu search failed query=%r", query)
            continue

        logger.info(
            "valyu_query_complete",
            extra={
                "event": "valyu_query_complete",
                "component": "adapters.valyu",
                "operation": "fetch_news",
                "stage": "fetch",
                "status": "ok",
                "duration_ms": int((time.perf_counter() - query_started) * 1000),
                "output_rows": len(resp.results),
                "window_start_date": start_date,
                "window_end_date": end_date,
                "reference_now_utc": effective_now.isoformat(),
            },
        )

        query_priced_rows = 0
        query_price_usd = 0.0
        for result in resp.results:
            data = result.model_dump()
            source_price = _extract_source_price(data)
            publication_ts = _parse_publication_timestamp(data.get("publication_date"))
            article_timestamp = publication_ts or effective_now
            if source_price is not None:
                query_priced_rows += 1
                query_price_usd += source_price
            articles.append(
                Article(
                    title=data.get("title", ""),
                    url=data.get("url"),
                    description=data.get("description", ""),
                    timestamp=article_timestamp,
                    publication_date=data.get("publication_date"),
                    source_price=source_price,
                    source=ArticleSource.valyu,
                    metadata=data,
                    query=query,
                )
            )
        total_priced_rows += query_priced_rows
        total_price_usd += query_price_usd
        logger.info(
            "valyu_price_summary",
            extra={
                "event": "valyu_price_summary",
                "component": "adapters.valyu",
                "operation": "fetch_news",
                "stage": "fetch",
                "status": "ok",
                "query": query,
                "output_rows": len(resp.results),
                "valyu_rows_with_price": query_priced_rows,
                "valyu_price_sum_usd": round(query_price_usd, 8),
                "window_start_date": start_date,
                "window_end_date": end_date,
                "reference_now_utc": effective_now.isoformat(),
            },
        )

    logger.info(
        "fetch_news_complete",
        extra={
            "event": "fetch_news_complete",
            "component": "adapters.valyu",
            "operation": "fetch_news",
            "stage": "fetch",
            "stage_status": "succeeded",
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "output_rows": len(articles),
            "valyu_rows_with_price": total_priced_rows,
            "valyu_price_sum_usd": round(total_price_usd, 8),
            "status": "ok",
            "window_start_date": start_date,
            "window_end_date": end_date,
            "reference_now_utc": effective_now.isoformat(),
        },
    )
    return articles
