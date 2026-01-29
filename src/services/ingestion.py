from __future__ import annotations

from typing import Iterable, List

from adapters.valyu import fetch_news
from models.article import Article


def collect_news(queries: Iterable[str], hours: int = 24, market: str = "GB") -> List[Article]:
    return fetch_news(queries=queries, hours=hours, market=market)
