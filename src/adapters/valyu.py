from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from valyu import Valyu

from config.settings import get_settings
from models.article import Article, ArticleSource

from utils.logging import get_logger

logger = get_logger(__name__)



def fetch_news(queries: Iterable[str], hours: int = 24, market: str = "GB") ->\
        List[Article]:
    logger.info("Fetching news: hours=%d market=%s", hours, market)
    valyu_config = get_settings().valyu_config
    api_key = valyu_config.api_key.get_secret_value()

    if not api_key:
        Exception("VALYU_API_KEY is not set")

    client = Valyu(api_key)
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
        if not resp or not resp.success:
            logger.warning("Valyu search failed: %r", resp)
            # logger.warning("Valyu search failed query=%r", query)
            continue

        logger.info("Valyu results query=%r count=%d", query, len(resp.results))


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

    logger.info("Fetch done: articles=%d", len(articles))
    return articles
