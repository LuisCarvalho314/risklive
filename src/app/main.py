from __future__ import annotations

from config.settings import get_config
from services.ingestion import collect_news


def run(hours: int = 1) -> int:
    config = get_config()
    articles = collect_news(config.categories + config.queries, hours=hours)
    return len(articles)
