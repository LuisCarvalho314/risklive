from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from valyu import Valyu

from config.settings import get_settings
from models.article import Article, ArticleSource


def fetch_news(queries: Iterable[str], hours: int = 24, market: str = "GB") -> List[Article]:
    settings = get_settings()
    api_key = settings.valyu_api_key
    if not api_key:
        return []

    client = Valyu(api_key)
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%d"
    )

    articles: List[Article] = []
    for query in queries:
        if not query:
            continue
        resp = client.search(
            query,
            search_type="news",
            start_date=start_date,
            end_date=end_date,
            max_num_results=10,
            url_only=True,
            response_length="short",
            country_code=market,
        )
        if not resp or not resp.success:
            continue
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
    return articles
