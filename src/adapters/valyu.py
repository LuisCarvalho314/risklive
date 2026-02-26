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



def fetch_news(queries: Iterable[str], hours: int = 24, market: str = "GB") ->\
        List[Article]:
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
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%d"
    )
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
            },
        )


        for result in resp.results:
            data = result.model_dump()
            articles.append(
                Article(
                    title=data.get("title", ""),
                    url=data.get("url"),
                    description=data.get("description", ""),
                    timestamp=datetime.now(timezone.utc),
                    publication_date=data.get("publication_date"),
                    source=ArticleSource.valyu,
                    metadata=data,
                    query=query,
                )
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
            "status": "ok",
        },
    )
    return articles
