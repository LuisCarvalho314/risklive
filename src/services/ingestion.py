"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from adapters.valyu import fetch_news
from models.article import Article


def collect_news(
    queries: Iterable[str],
    hours: int = 72,
    market: str = "GB",
    reference_now_utc: datetime | None = None,
) -> List[Article]:
    return fetch_news(
        queries=queries,
        hours=hours,
        market=market,
        reference_now_utc=reference_now_utc,
    )
